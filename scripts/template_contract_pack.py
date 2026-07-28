#!/usr/bin/env python3
"""Build EasySlides template contract sidecars from slot-guided template packs.

This is the small bridge borrowed from EasyPPT's template-library idea: keep
the existing EasySlides SVG/runtime layout folder, but add machine-readable
contracts for template discovery, layout roster, and slot replacement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS_ROOT = ROOT / "templates" / "layouts"

CONTRACT_FILES = {
    "template": "template.json",
    "layout_roster": "layout_roster.json",
    "slot_contracts": "slot_contracts.json",
    "links": "links.json",
}

SPECIAL_ROLE_MAP = {
    "toc": "agenda",
    "section_open": "section",
}

IMAGE_SLOT_HINTS = (
    "image",
    "photo",
    "logo",
    "diagram",
    "visual",
    "icon",
)
CANONICAL_SHELL_LIMIT = 5
CANONICAL_SHELL_MINIMUM = 3
REQUIRED_SHELL_ROLES = {"cover", "content", "ending"}
OPTIONAL_SHELL_ROLES = {"toc", "chapter"}
CANONICAL_SHELL_ROLES = REQUIRED_SHELL_ROLES | OPTIONAL_SHELL_ROLES

class TemplateContractError(RuntimeError):
    """Raised when a template folder cannot be compiled into contracts."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise TemplateContractError(f"missing required sidecar: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise TemplateContractError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TemplateContractError(f"{path.name} must contain a JSON object")
    return payload


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def template_prefix(template_id: str) -> str:
    words = [part for part in re.split(r"[^A-Za-z0-9]+", template_id) if part]
    letters = "".join(word[0] for word in words if word[0].isalpha())
    if len(letters) >= 2:
        return letters[:4].upper()
    cleaned = re.sub(r"[^A-Za-z0-9]", "", template_id)
    return (cleaned[:4] or "TPL").upper()


def rel_template_path(template_dir: Path, child: str) -> str:
    try:
        rel_dir = template_dir.resolve().relative_to(ROOT.resolve())
    except ValueError:
        rel_dir = Path("templates") / "layouts" / template_dir.name
    return (rel_dir / child).as_posix()


def role_fit_for_page(page: dict[str, Any]) -> list[str]:
    explicit = page.get("role_fit")
    if isinstance(explicit, list):
        values = [str(item) for item in explicit if str(item)]
        if values:
            return values
    role = str(page.get("story_role") or page.get("page_type") or "content")
    role = SPECIAL_ROLE_MAP.get(role, role)
    if role == "content":
        return ["content"]
    if role.endswith("_content"):
        role = role.removesuffix("_content")
    return [role]


def slot_is_image(slot: dict[str, Any]) -> bool:
    if slot.get("image_fit"):
        return True
    role = str(slot.get("role", "")).lower()
    kind = str(slot.get("kind", "")).lower()
    placement_role = str(slot.get("placement_role", "")).lower()
    slot_id = str(slot.get("slot_id", "")).lower()

    if role in {"main_figure", "exhibit_figure", "figure", "image", "photo", "logo", "card_icon"}:
        return True
    if kind in {"image", "photo", "logo", "icon", "figure"}:
        return True
    if placement_role in {"image", "photo", "logo", "icon", "figure"}:
        return True
    return any(hint in slot_id for hint in IMAGE_SLOT_HINTS)


def build_template_record(
    template_id: str,
    layouts: dict[str, Any],
    story: dict[str, Any],
    page_roles: list[str],
) -> OrderedDict[str, Any]:
    colors = layouts.get("colors") if isinstance(layouts.get("colors"), dict) else {}
    story_default = (
        story.get("default_scenario")
        or layouts.get("default_scenario")
        or layouts.get("scenario")
    )
    source_policy = OrderedDict(
        raw_pptx_in_catalog=False,
        raw_pptx_required_at_runtime=False,
        contains_local_paths=False,
        private_assets_role="build_reference_only",
        publishable_contract_sidecars=True,
    )
    text_fit_policy = layouts.get("text_fit_policy") if isinstance(layouts.get("text_fit_policy"), dict) else {}
    return OrderedDict(
        schema_version="easyslides.template_pack.v1",
        template_id=template_id,
        display_name=template_id.replace("_", " ").title(),
        availability="slot_guided_template_ready",
        recommended_template_route=str(
            (layouts.get("global_contract") or {}).get("replication_mode")
            or "slot_guided_mirror"
        ),
        output_contract="editable-native-pptx",
        style_system=layouts.get("style_system", template_id),
        layout_source_format="svg",
        runtime_source_of_truth="templates_layout_svgs",
        scenarios=[story_default] if story_default else [],
        roles=sorted(set(page_roles)),
        layout_count=len(layouts.get("pages", [])),
        primary_color=colors.get("primary", ""),
        text_fit_policy=OrderedDict(
            schema_version=text_fit_policy.get("schema_version"),
            check_command=f"python scripts/template_text_fit_check.py {template_id}",
            overflow_strategy_order=text_fit_policy.get("overflow_strategy_order", []),
        ),
        source_policy=source_policy,
    )


def build_layout_roster(
    template_dir: Path,
    template_id: str,
    layouts: dict[str, Any],
    catalog_by_id: dict[str, dict[str, Any]],
) -> OrderedDict[str, Any]:
    prefix = template_prefix(template_id)
    rows: list[OrderedDict[str, Any]] = []
    for index, page in enumerate(layouts.get("pages", []), start=1):
        page_id = str(page.get("id") or Path(str(page.get("svg", ""))).stem)
        svg = str(page.get("svg") or f"{page_id}.svg")
        catalog = catalog_by_id.get(page_id, {})
        role_fit = role_fit_for_page(page)
        layout_id = f"{prefix}-S{index:02d}"
        rows.append(
            OrderedDict(
                layout_id=layout_id,
                source_slide=page.get("source_slide", index),
                page_id=page_id,
                name=page_id.replace("_", " "),
                role_fit=role_fit,
                page_archetype=page.get("story_role", page.get("page_type", "content")),
                density_score=page.get("density_score", catalog.get("density_score")),
                slot_model=page.get("slot_model", page.get("page_type", "content")),
                svg_path=rel_template_path(template_dir, svg),
                layout_contract=f"{prefix.lower()}_s{index:02d}_{page_id}_contract",
                best_for=catalog.get("best_for", ""),
                avoid=catalog.get("avoid") or catalog.get("avoid_for", ""),
            )
        )
    return OrderedDict(
        schema_version="easyslides.template_layout_roster.v1",
        template_id=template_id,
        source="derived_from_layouts_page_catalog_and_story_structure",
        layouts=rows,
    )


def build_slot_contracts(
    template_id: str,
    layouts: dict[str, Any],
    roster: dict[str, Any],
) -> OrderedDict[str, Any]:
    slot_models = layouts.get("slot_models")
    if not isinstance(slot_models, dict):
        slot_models = {}

    rows: list[OrderedDict[str, Any]] = []
    pages = layouts.get("pages", [])
    for index, layout_row in enumerate(roster.get("layouts", [])):
        page = pages[index]
        model_id = str(page.get("slot_model") or page.get("page_type") or "content")
        model = slot_models.get(model_id, [])
        if not isinstance(model, list):
            model = []

        slots = [str(slot.get("slot_id")) for slot in model if slot.get("slot_id")]
        text_slots = [
            str(slot.get("slot_id"))
            for slot in model
            if slot.get("slot_id") and not slot_is_image(slot)
        ]
        image_slots = [
            str(slot.get("slot_id"))
            for slot in model
            if slot.get("slot_id") and slot_is_image(slot)
        ]

        rows.append(
            OrderedDict(
                layout_id=layout_row["layout_id"],
                page_id=layout_row["page_id"],
                svg_path=layout_row["svg_path"],
                role_fit=layout_row["role_fit"],
                slot_model=model_id,
                slots=slots,
                text_slots=text_slots,
                image_slots=image_slots,
                replacement="replace_declared_slots_preserve_template_geometry",
                slot_details=model,
            )
        )

    return OrderedDict(
        schema_version="easyslides.template_slot_contracts.v1",
        template_id=template_id,
        source="derived_from_layouts_json_slot_models",
        replacement_rule="replace_declared_slots_preserve_template_geometry",
        private_clone_required=False,
        text_fit_policy=layouts.get("text_fit_policy") if isinstance(layouts.get("text_fit_policy"), dict) else {},
        layouts=rows,
    )


def build_links(template_dir: Path, template_id: str) -> OrderedDict[str, Any]:
    def maybe(name: str) -> str | None:
        return rel_template_path(template_dir, name) if (template_dir / name).exists() else None

    return OrderedDict(
        schema_version="easyslides.template_links.v1",
        template_id=template_id,
        runtime_template_dir=rel_template_path(template_dir, ".").rstrip("/."),
        design_spec=maybe("design_spec.md"),
        layouts=maybe("layouts.json"),
        page_catalog=maybe("page_catalog.json"),
        story_structure=maybe("story_structure.json"),
        body_variants=maybe("body_variants.json"),
        component_catalog=maybe("component_catalog.json"),
        rules=maybe("rules.md"),
        template=rel_template_path(template_dir, CONTRACT_FILES["template"]),
        layout_roster=rel_template_path(template_dir, CONTRACT_FILES["layout_roster"]),
        slot_contracts=rel_template_path(template_dir, CONTRACT_FILES["slot_contracts"]),
        private_asset_bank_role="build_reference_only",
    )


def build_contract_pack(template_dir: Path) -> dict[str, OrderedDict[str, Any]]:
    template_dir = template_dir.resolve()
    if not template_dir.is_dir():
        raise TemplateContractError(f"template directory not found: {template_dir}")

    layouts = read_json(template_dir / "layouts.json")
    catalog = read_json(template_dir / "page_catalog.json")
    story = read_optional_json(template_dir / "story_structure.json")
    template_id = str(layouts.get("template_id") or template_dir.name)
    if template_id != template_dir.name:
        raise TemplateContractError(
            f"template_id {template_id!r} does not match directory {template_dir.name!r}"
        )

    package = read_optional_json(template_dir / "template_package.json")
    if isinstance(package.get("source_of_truth"), dict):
        try:
            from scripts.template_compiler import compile_template
        except ModuleNotFoundError:  # pragma: no cover
            from template_compiler import compile_template

        compiled = compile_template(template_dir)
        template_ir = compiled["template_ir"]
        roster_rows = []
        for index, shell in enumerate(template_ir.get("shells", []), start=1):
            roster_rows.append(
                OrderedDict(
                    layout_id=shell["shell_id"],
                    source_slide=index,
                    page_id=Path(shell["svg_path"]).stem,
                    name=shell["shell_id"].replace("_", " "),
                    role_fit=[shell["role"]],
                    page_archetype=shell.get("archetype", shell["role"]),
                    density_score=None,
                    slot_model=shell["role"],
                    svg_path=shell["svg_path"],
                    layout_contract=f"{template_id}/{shell['shell_id']}",
                    best_for=shell["role"],
                    avoid="",
                )
            )
        roster = OrderedDict(
            schema_version="easyslides.template_layout_roster.v1",
            template_id=template_id,
            source="derived_from_compiled_template_ir",
            layouts=roster_rows,
        )
        projections = compiled["projections"]
        return {
            "template": OrderedDict(projections["template.json"]),
            "layout_roster": roster,
            "slot_contracts": OrderedDict(projections["slot_contracts.json"]),
            "links": build_links(template_dir, template_id),
        }

    global_contract = layouts.get("global_contract") if isinstance(layouts.get("global_contract"), dict) else {}
    policy = global_contract.get("canonical_shell_policy")
    if policy in {
        "evidence_driven_three_to_five_stable_shells",
        "exactly_five_stable_shells_with_body_variants",
    }:
        pages = layouts.get("pages") if isinstance(layouts.get("pages"), list) else []
        roles = {
            str(page.get("shell_id") or page.get("page_id") or page.get("story_role") or page.get("page_type") or "")
            for page in pages
            if isinstance(page, dict)
        }
        if policy == "exactly_five_stable_shells_with_body_variants":
            valid_shell_count = len(pages) == CANONICAL_SHELL_LIMIT
            valid_roles = roles == CANONICAL_SHELL_ROLES
        else:
            valid_shell_count = CANONICAL_SHELL_MINIMUM <= len(pages) <= CANONICAL_SHELL_LIMIT
            valid_roles = REQUIRED_SHELL_ROLES <= roles <= CANONICAL_SHELL_ROLES
        if not valid_shell_count or not valid_roles:
            raise TemplateContractError(
                "canonical shell policy requires 3-5 public pages with required roles "
                "cover/content/ending and optional roles toc/chapter"
            )
        variants_ref = str(layouts.get("body_variants") or "body_variants.json")
        if not (template_dir / variants_ref).is_file():
            raise TemplateContractError(f"canonical shell policy requires {variants_ref}")
        roster_ref = str(layouts.get("source_page_roster") or "source_page_roster.json")
        if not (template_dir / roster_ref).is_file():
            raise TemplateContractError(f"canonical shell policy requires {roster_ref}")

    body_variants_path = template_dir / str(layouts.get("body_variants") or "body_variants.json")
    if body_variants_path.is_file():
        try:
            from scripts.body_variant_contract import validate_body_variant_contract
        except ModuleNotFoundError:  # pragma: no cover
            from body_variant_contract import validate_body_variant_contract

        component_report = validate_body_variant_contract(template_dir)
        if component_report["status"] != "pass":
            first = component_report["issues"][0]
            raise TemplateContractError(
                "body variant component contract failed: "
                f"{first.get('code')} at {first.get('path')}: {first.get('message')}"
            )

    catalog_pages = catalog.get("archetypes") or catalog.get("pages", [])
    if not isinstance(catalog_pages, list):
        raise TemplateContractError("page_catalog.json pages must be a list")
    catalog_by_id = {
        str(page.get("id")): page
        for page in catalog_pages
        if isinstance(page, dict) and page.get("id")
    }

    roster = build_layout_roster(template_dir, template_id, layouts, catalog_by_id)
    role_list = [role for row in roster["layouts"] for role in row["role_fit"]]
    template = build_template_record(template_id, layouts, story, role_list)
    slots = build_slot_contracts(template_id, layouts, roster)
    links = build_links(template_dir, template_id)
    return {
        "template": template,
        "layout_roster": roster,
        "slot_contracts": slots,
        "links": links,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_contract_pack(template_dir: Path) -> list[Path]:
    template_dir = template_dir.resolve()
    pack = build_contract_pack(template_dir)
    written: list[Path] = []
    for key, filename in CONTRACT_FILES.items():
        path = template_dir / filename
        write_json(path, pack[key])
        written.append(path)
    return written


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_template_arg(value: str) -> Path:
    path = Path(value)
    if path.is_dir():
        return path
    return LAYOUTS_ROOT / value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build template.json/layout_roster.json/slot_contracts.json/links.json for a template."
    )
    parser.add_argument("template", help="Template id under templates/layouts or a template directory path.")
    parser.add_argument("--check", action="store_true", help="Validate pack generation without writing files.")
    args = parser.parse_args(argv)

    template_dir = resolve_template_arg(args.template)
    try:
        if args.check:
            pack = build_contract_pack(template_dir)
            print(json.dumps({"status": "pass", "template_id": pack["template"]["template_id"]}, ensure_ascii=False))
        else:
            written = write_contract_pack(template_dir)
            print(f"Wrote {len(written)} contract sidecar(s) for {template_dir.name}:")
            for path in written:
                print(f"- {display_path(path)}")
    except TemplateContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
