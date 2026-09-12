import copy
import json

import pytest

from scripts.clarification_gate import (
    ClarificationError, answer_clarification_request, build_clarification_request,
    main, next_clarification_question, require_confirmed, validate_clarification_request,
)


def known():
    return dict(academic_goal="组会，比较城市交通多模态预测的方法和局限",
                audience="跨专业研究生", talk_timing="15分钟讲述，5分钟问答",
                style_intent="严格按给定图片模板", content_boundaries="原图保留，允许重组",
                production_scheme="image_full_rebuild", reconstruction_mode="preserve_complex_images")


def test_source_choice_creates_conditional_followup():
    request = build_clarification_request("image_reconstruction", known=known(), academic=True)
    assert next_clarification_question(request)["question_id"] == "source_policy"
    request = answer_clarification_request(request, {"source_policy": "research"})
    question = next_clarification_question(request)
    assert question["question_id"] == "research_scope"
    assert "options" not in question["questions"][0]
    assert "material_inventory" not in request["pending_question_ids"]
    request = answer_clarification_request(request, {"research_scope": "2020–2026；交通传感器、天气及事件融合；研究综述"})
    assert request["status"] == "confirmed"
    assert next_clarification_question(request)["questions"] == []


def test_material_inspection_is_not_a_user_question(tmp_path):
    request = build_clarification_request("image_reconstruction", known={**known(), "source_policy": "supplied_only"}, academic=True)
    before = copy.deepcopy(request)
    question = next_clarification_question(request)
    assert question["status"] == "needs_material_inspection"
    assert question["questions"] == []
    assert before == request
    path = tmp_path / "clarification_request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ClarificationError):
        require_confirmed(path)
    request = answer_clarification_request(request, {"material_inventory": "paper.pdf：正文已读；Fig.2 p4 为主要结果；参考模板仅作视觉参考"}, confirmed_by="inspection:paper.pdf:p4")
    path.write_text(json.dumps(request), encoding="utf-8")
    assert require_confirmed(path)["answer_origins"]["material_inventory"]["by"] == "inspection:paper.pdf:p4"


def test_hybrid_requires_both_and_preserves_free_text():
    request = build_clarification_request("image_reconstruction", known={**known(), "source_policy": "hybrid"}, academic=True)
    assert set(request["pending_question_ids"]) == {"material_inventory", "research_scope"}
    with pytest.raises(ClarificationError):
        answer_clarification_request(request, {"research_scope": " "})
    text = "2024年至今；仅原始论文，不包括预印本"
    request = answer_clarification_request(request, {"research_scope": text})
    assert request["decisions"]["research_scope"] == text
    assert request["status"] != "confirmed"


def test_cannot_remove_required_academic_question():
    request = build_clarification_request("image_reconstruction", known={**known(), "source_policy": "research"}, academic=True)
    request.update(question_bank=[], questions=[], pending_question_ids=[], status="confirmed")
    assert validate_clarification_request(request)["status"] == "fail"


@pytest.mark.parametrize("value", [True, 15, ["expert"], {"known": True}, " "])
def test_prefilled_text_requires_real_text(value):
    with pytest.raises(ClarificationError):
        build_clarification_request("image_reconstruction", known={**known(), "audience": value}, academic=True)


def test_changed_source_policy_removes_obsolete_dependencies():
    request = build_clarification_request("image_reconstruction", known=known(), academic=True)
    request = answer_clarification_request(request, {"source_policy": "hybrid"})
    request = answer_clarification_request(request, {"material_inventory": "paper.pdf p1-4 已检查"}, confirmed_by="inspection")
    request = answer_clarification_request(request, {"source_policy": "research"})
    assert request["pending_question_ids"] == ["research_scope"]
    assert "material_inventory" not in request["decisions"]
    assert "material_inventory" not in request["answers"]
    assert validate_clarification_request(request)["status"] == "pass"


def test_cli_academic_init_and_free_text_answer(tmp_path, capsys):
    path = tmp_path / "clarification_request.json"
    assert main(["init", "--route", "new_deck", "--academic", "--out", str(path)]) == 0
    assert main(["answer", str(path), "--answer", "academic_goal=论文答辩，解释我的贡献"]) == 0
    request = json.loads(path.read_text(encoding="utf-8"))
    assert request["academic_intake"] is True
    assert request["decisions"]["academic_goal"] == "论文答辩，解释我的贡献"
    assert next_clarification_question(request)["question_id"] == "source_policy"


def test_plan_gate_requires_confirmed_brief_handoff(tmp_path, monkeypatch):
    from scripts import deck_plan_contract
    request = build_clarification_request("image_reconstruction", known={
        **known(), "source_policy": "research", "research_scope": "2020–2026 交通预测原始论文",
    }, academic=True)
    (tmp_path / "clarification_request.json").write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr(deck_plan_contract, "validate_deck_plan", lambda *a, **k: {"status": "pass", "issues": [], "issue_count": 0})
    path = tmp_path / "deck_plan.json"
    path.write_text(json.dumps({"academic_brief": request["decisions"]}), encoding="utf-8")
    assert deck_plan_contract.validate_deck_plan_file(path)["status"] == "pass"
    path.write_text(json.dumps({"academic_brief": {"audience": "changed"}}), encoding="utf-8")
    report = deck_plan_contract.validate_deck_plan_file(path)
    assert report["issues"][0]["code"] == "DECK-PLAN-ACADEMIC-BRIEF"
