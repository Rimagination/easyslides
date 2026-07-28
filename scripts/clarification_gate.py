#!/usr/bin/env python3
"""Build and validate the EasySlides pre-execution clarification contract.

The chat layer asks the user the questions described here. This module keeps
the question catalog and the answer state machine deterministic so downstream
steps cannot silently replace an unresolved decision with a default.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.clarification_request.v1"
MAX_QUESTIONS_PER_ROUND = 3
TERMINAL_STATUSES = {"confirmed", "cancelled"}


def _option(option_id: str, label: str, impact: str) -> dict[str, str]:
    return {"id": option_id, "label": label, "impact": impact}


def _question(
    question_id: str,
    field: str,
    prompt: str,
    options: list[dict[str, str]],
    recommended_option_id: str,
    why: str,
) -> dict[str, Any]:
    option_ids = {item["id"] for item in options}
    if recommended_option_id not in option_ids:
        raise ValueError(f"recommended option {recommended_option_id!r} is not defined for {question_id!r}")
    return {
        "id": question_id,
        "field": field,
        "prompt": prompt,
        "options": options,
        "recommended_option_id": recommended_option_id,
        "why": why,
        "blocking": True,
    }


QUESTION_CATALOG: dict[str, list[dict[str, Any]]] = {
    "new_deck": [
        _question(
            "purpose",
            "purpose",
            "这份 PPT 的主要用途是什么？",
            [
                _option("defense", "答辩/学术汇报", "强调研究问题、方法、证据链和结论。"),
                _option("project_report", "项目/阶段汇报", "强调进展、风险、决策和下一步行动。"),
                _option("teaching", "教学/培训", "强调概念递进、例子和学习节奏。"),
                _option("outreach", "科普/公开分享", "降低术语密度，强化故事和直观解释。"),
            ],
            "defense",
            "用途会决定内容结构、页间节奏和证据密度。",
        ),
        _question(
            "audience",
            "audience",
            "现场主要听众是哪一类？",
            [
                _option("committee", "评审/答辩委员会", "默认听众专业，突出方法可靠性和贡献。"),
                _option("peers", "同行/专业团队", "保留专业细节，强化比较和可复现性。"),
                _option("general", "非专业听众", "解释术语，减少公式和领域内缩写。"),
            ],
            "peers",
            "听众决定术语解释深度和页面信息密度。",
        ),
        _question(
            "story_policy",
            "story_policy",
            "内容组织采用哪种方式？",
            [
                _option("source_order", "基本保持原材料顺序", "优先保留来源结构，适合忠实转化。"),
                _option("restructure", "围绕核心结论重新组织", "允许调整顺序、合并和拆分页面。"),
                _option("extract_core", "只提取核心信息", "删减背景和次要证据，形成短版演示。"),
            ],
            "restructure",
            "这是页数、叙事和模板选择的关键分叉。",
        ),
        _question(
            "page_budget",
            "page_budget",
            "期望页面规模如何？",
            [
                _option("source_adaptive", "根据材料量自适应", "由证据量和叙事完整性决定页数。"),
                _option("short", "8–10 页短版", "适合快速汇报，内容需要高度压缩。"),
                _option("standard", "12–15 页标准版", "在完整性和演示节奏之间平衡。"),
                _option("deep", "16 页以上深度版", "允许展开方法、结果和补充证据。"),
            ],
            "source_adaptive",
            "页面规模会影响拆页、组件密度和内容取舍。",
        ),
        _question(
            "canvas_format",
            "canvas_format",
            "画布比例采用哪一种？",
            [
                _option("16:9", "16:9 宽屏", "适合现代会议室、线上分享和默认 EasySlides 模板。"),
                _option("4:3", "4:3 标准", "适合旧设备或明确要求传统比例的场景。"),
            ],
            "16:9",
            "比例会影响模板筛选和所有页面几何。",
        ),
    ],
    "paper_deck": [
        _question(
            "presentation_mode",
            "presentation_mode",
            "论文 PPT 的汇报深度是什么？",
            [
                _option("concise", "10 分钟以内精简版", "只保留问题、方法、核心结果和结论。"),
                _option("standard", "15–20 分钟标准版", "完整覆盖研究链条和主要证据。"),
                _option("deep", "深入研讨版", "展开方法细节、局限和补充结果。"),
            ],
            "standard",
            "汇报时长决定论文内容的压缩比例。",
        ),
        _question(
            "audience",
            "audience",
            "论文 PPT 的主要听众是哪一类？",
            [
                _option("specialists", "本领域专家", "可直接使用领域术语，突出方法和边界。"),
                _option("mixed", "跨领域研究者", "需要解释关键概念和研究意义。"),
                _option("general", "非专业听众", "以问题、现象和结果的直观理解为主。"),
            ],
            "mixed",
            "听众决定论文术语、图表和背景的解释深度。",
        ),
        _question(
            "evidence_scope",
            "evidence_scope",
            "论文中的证据如何取舍？",
            [
                _option("all_key", "保留所有关键图表", "强调完整证据链，页面数量可能增加。"),
                _option("selected", "只保留最能支撑结论的证据", "减少页面，突出主线。"),
                _option("methods_first", "方法和可复现性优先", "适合方法学报告或技术评审。"),
            ],
            "selected",
            "证据取舍会直接影响页数、图表资产和讲述重点。",
        ),
        _question(
            "story_policy",
            "story_policy",
            "论文叙事是否允许脱离原文顺序？",
            [
                _option("paper_order", "保持论文顺序", "按背景、方法、结果、讨论组织。"),
                _option("conclusion_first", "结论先行", "先给核心发现，再回溯证据和方法。"),
            ],
            "conclusion_first",
            "会影响 action title、目录和结果页排序。",
        ),
    ],
    "pptx_beautify": [
        _question(
            "preservation",
            "preservation",
            "美化时是否允许改变页面结构？",
            [
                _option("strict", "保留页数、顺序和可见文字", "只做保守的颜色、字体和间距修正。"),
                _option("layout_repair", "允许重排页面但不改变事实", "可以调整布局、拆分拥挤页面。"),
                _option("restructure", "允许重新组织内容", "将现有 PPT 当作材料重新生成。"),
            ],
            "strict",
            "这是美化路线和重构路线的关键分叉。",
        ),
        _question(
            "editing_scope",
            "editing_scope",
            "文字和图片可以修改到什么程度？",
            [
                _option("visual_only", "只改视觉，不改文字和图片", "最大限度保留原稿内容。"),
                _option("shorten_text", "允许压缩文字", "可解决溢出和密度问题，但不改事实。"),
                _option("replace_assets", "允许替换或补充图片", "可修复低质量图片和缺失视觉资产。"),
            ],
            "visual_only",
            "编辑范围决定是否需要内容确认和来源追踪。",
        ),
    ],
    "template_fill": [
        _question(
            "template_fidelity",
            "template_fidelity",
            "模板填充时，模板视觉需要保留到什么程度？",
            [
                _option("locked", "严格保持模板几何和视觉", "只替换已声明内容槽位。"),
                _option("adaptive", "保留风格但允许适配布局", "允许按内容密度选择相邻布局。"),
                _option("inspired", "只借鉴风格和组件", "允许重新设计页面结构。"),
            ],
            "locked",
            "决定使用原生填充、槽位投影还是重新生成。",
        ),
        _question(
            "page_policy",
            "page_policy",
            "页面数量和顺序是否可以变化？",
            [
                _option("preserve", "保持模板页面数量和顺序", "所有页面都要找到对应内容。"),
                _option("select", "可以选择部分模板页面", "只使用适合当前内容的页面。"),
                _option("extend", "允许增删和扩展页面", "可以形成完整的新叙事。"),
            ],
            "select",
            "会影响模板绑定、页面规划和最终导出页数。",
        ),
    ],
    "pptx_distill": [
        _question(
            "distill_goal",
            "distill_goal",
            "蒸馏 PPT 的主要目标是什么？",
            [
                _option("faithful_reuse", "忠实提取为可复用模板", "优先保留页面角色、几何和视觉语言。"),
                _option("component_library", "提取组件资产库", "优先识别卡片、图表、页眉和可组合模块。"),
                _option("both", "模板和组件库都要", "同时保留页面级模板和组件级资产。"),
            ],
            "both",
            "决定蒸馏产物的深度和 promotion gate 范围。",
        ),
        _question(
            "fidelity_scope",
            "fidelity_scope",
            "复杂视觉效果如何处理？",
            [
                _option("editable_first", "优先可编辑", "复杂效果允许近似，但文字和结构保持原生。"),
                _option("visual_first", "优先视觉一致", "复杂效果可使用受控栅格资产。"),
                _option("hybrid", "文字结构可编辑，复杂装饰保真", "在编辑性和视觉一致性之间折中。"),
            ],
            "hybrid",
            "决定 SVG/PPTX 转换策略和资产类型。",
        ),
    ],
    "native_enhance": [
        _question(
            "enhancement_scope",
            "enhancement_scope",
            "已有 PPT 需要增强哪些部分？",
            [
                _option("notes_media", "备注、音频、动画或切换", "保持可见页面稳定，只修改演示附加信息。"),
                _option("visual", "字体、颜色和视觉层级", "允许修改主题和页面视觉，但保留结构。"),
                _option("structure", "页面结构和内容也可调整", "必要时进入重构路线。"),
            ],
            "notes_media",
            "增强范围决定是否允许改变用户已经看到的页面。",
        ),
        _question(
            "visual_stability",
            "visual_stability",
            "现有页面是否需要保持视觉稳定？",
            [
                _option("locked", "必须保持可见页面稳定", "只做明确授权的附加修改。"),
                _option("improve", "允许修复明显布局问题", "可调整溢出、重叠和错位。"),
            ],
            "locked",
            "决定是 native append-only，还是进入 beautify/rebuild 路线。",
        ),
    ],
}

ROUTE_ALIASES = {
    "create": "new_deck",
    # Backward-compatible alias for pre-0.1.1 callers. The user-facing
    # canonical skill and route name is now `easyslides`.
    "academic-pptx": "new_deck",
    "easyslides": "new_deck",
    "paper": "paper_deck",
    "literature-report": "paper_deck",
    "beautify": "pptx_beautify",
    "template-fill-pptx": "template_fill",
    "distill": "pptx_distill",
    "pptx-to-easyslides-template": "pptx_distill",
    "enhance": "native_enhance",
}


class ClarificationError(ValueError):
    """Raised when clarification state cannot authorize execution."""


def canonical_route(route: str) -> str:
    value = str(route or "").strip()
    value = ROUTE_ALIASES.get(value, value)
    if value not in QUESTION_CATALOG:
        choices = ", ".join(sorted(QUESTION_CATALOG))
        raise ClarificationError(f"unknown clarification route {route!r}; choose one of: {choices}")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _known_value(known: dict[str, Any], field: str) -> bool:
    value = known.get(field)
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _question_ids(request: dict[str, Any]) -> list[str]:
    return [str(item["id"]) for item in request.get("question_bank", []) if isinstance(item, dict)]


def _unanswered_ids(request: dict[str, Any]) -> list[str]:
    answers = request.get("answers", {})
    return [question_id for question_id in _question_ids(request) if question_id not in answers]


def _refresh_round(request: dict[str, Any]) -> dict[str, Any]:
    unanswered = _unanswered_ids(request)
    by_id = {str(item["id"]): item for item in request.get("question_bank", []) if isinstance(item, dict)}
    current_ids = unanswered[:MAX_QUESTIONS_PER_ROUND]
    request["questions"] = [copy.deepcopy(by_id[item]) for item in current_ids]
    request["pending_question_ids"] = unanswered
    request["blocking_question_ids"] = _question_ids(request)
    if not unanswered:
        request["status"] = "confirmed"
        request["confirmed_at"] = request.get("confirmed_at") or _now()
    else:
        request["status"] = "needs_confirmation"
        request.pop("confirmed_at", None)
    request["updated_at"] = _now()
    return request


def build_clarification_request(
    route: str,
    *,
    known: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    canonical = canonical_route(route)
    known_fields = known or {}
    question_bank = [
        copy.deepcopy(question)
        for question in QUESTION_CATALOG[canonical]
        if not _known_value(known_fields, str(question["field"]))
    ]
    request: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_confirmation" if question_bank else "confirmed",
        "route": canonical,
        "title": title or "EasySlides execution clarification",
        "created_at": _now(),
        "updated_at": _now(),
        "questions": [],
        "question_bank": question_bank,
        "pending_question_ids": [],
        "blocking_question_ids": [],
        "answers": {},
        "decisions": copy.deepcopy(known_fields),
        "assumptions": [],
    }
    return _refresh_round(request)


def validate_clarification_request(request: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(request, dict):
        return {"schema_version": SCHEMA_VERSION, "status": "fail", "issues": [{"code": "REQUEST-TYPE", "message": "request must be an object"}]}
    if request.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "REQUEST-SCHEMA", "message": f"schema_version must be {SCHEMA_VERSION}"})
    try:
        canonical = canonical_route(str(request.get("route", "")))
        if canonical != request.get("route"):
            issues.append({"code": "REQUEST-ROUTE", "message": "route must use its canonical id"})
    except ClarificationError as exc:
        issues.append({"code": "REQUEST-ROUTE", "message": str(exc)})

    bank = request.get("question_bank")
    answers = request.get("answers")
    if not isinstance(bank, list) or not bank:
        if request.get("status") != "confirmed":
            issues.append({"code": "REQUEST-QUESTIONS", "message": "question_bank must be non-empty until confirmed"})
        bank = bank if isinstance(bank, list) else []
    if not isinstance(answers, dict):
        issues.append({"code": "REQUEST-ANSWERS", "message": "answers must be an object"})
        answers = {}

    ids: set[str] = set()
    ordered_ids: list[str] = []
    option_map: dict[str, set[str]] = {}
    for index, question in enumerate(bank):
        path = f"question_bank[{index}]"
        if not isinstance(question, dict):
            issues.append({"code": "QUESTION-TYPE", "message": f"{path} must be an object"})
            continue
        question_id = str(question.get("id", ""))
        if not question_id or question_id in ids:
            issues.append({"code": "QUESTION-ID", "message": f"{path}.id must be unique and non-empty"})
        ids.add(question_id)
        if question_id:
            ordered_ids.append(question_id)
        options = question.get("options")
        option_ids: set[str] = set()
        if not isinstance(options, list) or len(options) < 2:
            issues.append({"code": "QUESTION-OPTIONS", "message": f"{path}.options must contain at least two choices"})
        else:
            for option in options:
                if not isinstance(option, dict) or not option.get("id") or not option.get("label"):
                    issues.append({"code": "OPTION-SHAPE", "message": f"{path}.options contains an invalid choice"})
                    continue
                option_ids.add(str(option["id"]))
        recommended = question.get("recommended_option_id")
        if recommended not in option_ids:
            issues.append({"code": "QUESTION-RECOMMENDATION", "message": f"{path}.recommended_option_id must name an option"})
        option_map[question_id] = option_ids

    for question_id, answer in answers.items():
        if question_id not in ids:
            issues.append({"code": "ANSWER-QUESTION", "message": f"answer refers to unknown question {question_id!r}"})
        elif answer not in option_map.get(question_id, set()):
            issues.append({"code": "ANSWER-OPTION", "message": f"answer {answer!r} is not valid for {question_id!r}"})

    unanswered = [question_id for question_id in ordered_ids if question_id not in answers]
    status = request.get("status")
    if status not in {"needs_confirmation", "confirmed", "cancelled"}:
        issues.append({"code": "REQUEST-STATUS", "message": "status must be needs_confirmation, confirmed, or cancelled"})
    if status == "confirmed" and unanswered:
        issues.append({"code": "REQUEST-UNANSWERED", "message": "confirmed request still has blocking questions"})
    if status == "needs_confirmation" and not unanswered:
        issues.append({"code": "REQUEST-STALE-STATUS", "message": "all questions are answered but status is not confirmed"})

    expected_pending = unanswered
    if request.get("pending_question_ids") != expected_pending:
        issues.append({"code": "REQUEST-PENDING", "message": "pending_question_ids does not match unanswered questions"})
    current_ids = [str(item.get("id")) for item in request.get("questions", []) if isinstance(item, dict)]
    expected_current = unanswered[:MAX_QUESTIONS_PER_ROUND]
    if current_ids != expected_current:
        issues.append({"code": "REQUEST-ROUND", "message": "questions does not match the current clarification round"})

    return {
        "schema_version": "easyslides.clarification_report.v1",
        "status": "pass" if not issues else "fail",
        "request_status": status,
        "blocking_count": len(unanswered),
        "current_round_count": len(current_ids),
        "issues": issues,
    }


def answer_clarification_request(
    request: dict[str, Any],
    answers: dict[str, str],
    *,
    confirmed_by: str = "user",
) -> dict[str, Any]:
    report = validate_clarification_request(request)
    if report["status"] != "pass":
        raise ClarificationError("cannot answer an invalid clarification request")
    if request.get("status") in TERMINAL_STATUSES:
        raise ClarificationError(f"cannot answer a {request['status']} request")

    by_id = {str(item["id"]): item for item in request["question_bank"]}
    next_answers = dict(request.get("answers", {}))
    for question_id, option_id in answers.items():
        if question_id not in by_id:
            raise ClarificationError(f"unknown question id: {question_id}")
        valid_options = {str(option["id"]) for option in by_id[question_id]["options"]}
        if option_id in {"recommended", "recommendation", "按推荐"}:
            option_id = str(by_id[question_id]["recommended_option_id"])
        if option_id not in valid_options:
            raise ClarificationError(f"invalid option {option_id!r} for question {question_id!r}")
        next_answers[question_id] = option_id

    request["answers"] = next_answers
    decisions = dict(request.get("decisions", {}))
    for question in request["question_bank"]:
        question_id = str(question["id"])
        if question_id in next_answers:
            decisions[str(question["field"])] = next_answers[question_id]
    request["decisions"] = decisions
    request["last_answered_by"] = confirmed_by
    return _refresh_round(request)


def require_confirmed(request_path: str | Path) -> dict[str, Any]:
    path = Path(request_path)
    if not path.exists():
        raise ClarificationError(f"clarification request not found: {path}")
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClarificationError(f"cannot read clarification request: {path}") from exc
    report = validate_clarification_request(request)
    if report["status"] != "pass" or request.get("status") != "confirmed":
        raise ClarificationError(
            f"clarification is not confirmed: {path} ({report['blocking_count']} blocking question(s) remain)"
        )
    return request


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and validate the EasySlides clarification gate.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog", help="Print route-specific question templates.")
    catalog.add_argument("--route", default=None, help="Optional route id or alias.")

    init = subparsers.add_parser("init", help="Create a clarification request.")
    init.add_argument("--route", required=True, help="Route id or alias.")
    init.add_argument("--out", required=True, type=Path)
    init.add_argument("--known-json", type=Path, help="JSON object of values already explicitly supplied by the user.")
    init.add_argument("--title")

    validate = subparsers.add_parser("validate", help="Validate a clarification request.")
    validate.add_argument("request", type=Path)

    answer = subparsers.add_parser("answer", help="Apply selected options to a request and advance its round.")
    answer.add_argument("request", type=Path)
    answer.add_argument("--answer", action="append", default=[], help="Answer as QUESTION_ID=OPTION_ID. Repeatable.")
    answer.add_argument("--by", default="user", help="Answer source label.")

    require = subparsers.add_parser("require", help="Exit successfully only when a request is confirmed.")
    require.add_argument("request", type=Path)
    return parser


def _parse_answers(values: list[str]) -> dict[str, str]:
    answers: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ClarificationError(f"answer must use QUESTION_ID=OPTION_ID syntax: {value}")
        question_id, option_id = value.split("=", 1)
        if not question_id.strip() or not option_id.strip():
            raise ClarificationError(f"answer contains an empty id: {value}")
        answers[question_id.strip()] = option_id.strip()
    return answers


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "catalog":
            if args.route:
                route = canonical_route(args.route)
                print(json.dumps({"route": route, "questions": QUESTION_CATALOG[route]}, ensure_ascii=False, indent=2))
            else:
                print(json.dumps(QUESTION_CATALOG, ensure_ascii=False, indent=2))
            return 0
        if args.command == "init":
            known = _read_json(args.known_json) if args.known_json else {}
            request = build_clarification_request(args.route, known=known, title=args.title)
            _write_json(args.out, request)
            print(json.dumps(request, ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate":
            report = validate_clarification_request(_read_json(args.request))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "pass" else 2
        if args.command == "answer":
            request = _read_json(args.request)
            updated = answer_clarification_request(request, _parse_answers(args.answer), confirmed_by=args.by)
            _write_json(args.request, updated)
            print(json.dumps(updated, ensure_ascii=False, indent=2))
            return 0
        if args.command == "require":
            request = require_confirmed(args.request)
            print(json.dumps({"status": "pass", "route": request["route"], "decisions": request["decisions"]}, ensure_ascii=False, indent=2))
            return 0
    except (ClarificationError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
