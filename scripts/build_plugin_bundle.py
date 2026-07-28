#!/usr/bin/env python3
"""Build a physical, privacy-safe EasySlides plugin bundle.

Codex plugin caching does not follow nested Windows junctions reliably.  This
builder copies the plugin runtime into a real directory and deliberately omits
projects, source PPTX/PDF files, distillation evidence, tests, and legacy
standalone skills.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILLS = ("easyslides", "easyslides-distill", "easyslides-clarify")
ROOT_FILES = (
    "SKILL.md",
    "ARCHITECTURE.md",
    "PLUGIN.md",
    "README.md",
    "requirements.txt",
)
RUNTIME_TEMPLATE_DIRS = (
    "brands",
    "cards",
    "charts",
    "page_layouts",
    "style_packs",
)
FORBIDDEN_SUFFIXES = {".ppt", ".pptx", ".pdf", ".doc", ".docx"}
VOLATILE_QA_FILES = {
    "human_review.json",
    "production_gate.json",
    "production_gate_previsual.json",
}
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]")


def _ignore_runtime(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {"__pycache__", ".pytest_cache", ".git", "node_modules"}
        or name in VOLATILE_QA_FILES
        or name.endswith((".pyc", ".pyo", ".tmp"))
        or Path(name).suffix.lower() in FORBIDDEN_SUFFIXES
    }


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        return
    shutil.copytree(source, target, ignore=_ignore_runtime)


def _selected_layout_ids() -> list[str]:
    layouts_root = ROOT / "templates" / "layouts"
    payload = json.loads((layouts_root / "layouts_index.json").read_text(encoding="utf-8"))
    aliases = json.loads((layouts_root / "aliases.json").read_text(encoding="utf-8"))
    selected = set(payload)
    selected.update(str(value) for value in aliases.values())
    return sorted(layout_id for layout_id in selected if (layouts_root / layout_id).is_dir())


def _copy_references(target_root: Path) -> None:
    source_root = ROOT / "references"
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        if relative.parts and relative.parts[0] in {"assets", "template_asset_sources"}:
            continue
        keep_text = source.suffix.lower() in {".md", ".yaml", ".yml"}
        keep_root_json = source.suffix.lower() == ".json" and relative.parent == Path(".")
        if not (keep_text or keep_root_json):
            continue
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _copy_templates(target_root: Path) -> list[str]:
    source_root = ROOT / "templates"
    target_root.mkdir(parents=True, exist_ok=True)
    for filename in ("README.md",):
        source = source_root / filename
        if source.is_file():
            shutil.copy2(source, target_root / filename)

    layouts_source = source_root / "layouts"
    layouts_target = target_root / "layouts"
    layouts_target.mkdir(parents=True, exist_ok=True)
    for filename in ("README.md", "layouts_index.json", "aliases.json"):
        shutil.copy2(layouts_source / filename, layouts_target / filename)
    selected_layouts = _selected_layout_ids()
    for layout_id in selected_layouts:
        _copy_tree(layouts_source / layout_id, layouts_target / layout_id)
    if (layouts_source / "assets").is_dir():
        _copy_tree(layouts_source / "assets", layouts_target / "assets")

    components_source = source_root / "components"
    components_target = target_root / "components"
    for dirname in ("gallery", "packages", "packs"):
        _copy_tree(components_source / dirname, components_target / dirname)

    for dirname in RUNTIME_TEMPLATE_DIRS:
        _copy_tree(source_root / dirname, target_root / dirname)

    # Keep a useful lightweight icon set in the installed plugin. The complete
    # 11k+ icon repository remains available in the development checkout.
    icons_source = source_root / "icons"
    icons_target = target_root / "icons"
    icons_target.mkdir(parents=True, exist_ok=True)
    for filename in ("README.md", "icons_manifest.js"):
        source = icons_source / filename
        if source.is_file():
            shutil.copy2(source, icons_target / filename)
    for dirname in ("chunk-filled", "lucide"):
        _copy_tree(icons_source / dirname, icons_target / dirname)
    return selected_layouts


def _validate_bundle(output_dir: Path) -> dict[str, object]:
    skill_names = sorted(path.name for path in (output_dir / "skills").iterdir() if path.is_dir())
    if skill_names != sorted(CANONICAL_SKILLS):
        raise ValueError(f"bundle skill set is not canonical: {skill_names}")
    forbidden = [
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden:
        raise ValueError(f"private/source document types entered plugin bundle: {forbidden[:10]}")
    links = []
    for path in output_dir.rglob("*"):
        is_junction = getattr(path, "is_junction", lambda: False)()
        if path.is_symlink() or is_junction:
            links.append(path.relative_to(output_dir).as_posix())
    if links:
        raise ValueError(f"plugin bundle contains links instead of physical files: {links[:10]}")
    invalid_json = []
    for path in output_dir.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            invalid_json.append(f"{path.relative_to(output_dir).as_posix()}: {exc}")
    if invalid_json:
        raise ValueError(f"plugin bundle contains invalid JSON: {invalid_json[:10]}")
    local_paths = []
    for path in output_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml", ".md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if WINDOWS_ABSOLUTE_PATH.search(text):
            local_paths.append(path.relative_to(output_dir).as_posix())
    if local_paths:
        raise ValueError(f"plugin bundle contains machine-local absolute paths: {local_paths[:10]}")
    files = [path for path in output_dir.rglob("*") if path.is_file()]
    return {
        "file_count": len(files),
        "size_bytes": sum(path.stat().st_size for path in files),
        "skills": skill_names,
    }


def build_bundle(output_dir: Path) -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir == ROOT or output_dir in ROOT.parents:
        raise ValueError("refusing to replace the repository or one of its parents")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    _copy_tree(ROOT / ".codex-plugin", output_dir / ".codex-plugin")
    _copy_tree(ROOT / "assets", output_dir / "assets")
    for filename in ROOT_FILES:
        source = ROOT / filename
        if source.is_file():
            shutil.copy2(source, output_dir / filename)
    for skill_name in CANONICAL_SKILLS:
        _copy_tree(ROOT / "skills" / skill_name, output_dir / "skills" / skill_name)
    _copy_tree(ROOT / "workflows", output_dir / "workflows")
    _copy_tree(ROOT / "scripts", output_dir / "scripts")
    _copy_references(output_dir / "references")
    selected_layouts = _copy_templates(output_dir / "templates")

    validation = _validate_bundle(output_dir)
    manifest = {
        "schema_version": "easyslides.plugin_bundle.v1",
        "status": "pass",
        "plugin": "easyslides",
        "skills": list(CANONICAL_SKILLS),
        "layouts": selected_layouts,
        "privacy_policy": {
            "projects_included": False,
            "source_documents_included": False,
            "distillation_evidence_included": False,
            "legacy_standalone_skills_included": False,
        },
        **validation,
    }
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a physical privacy-safe EasySlides Codex plugin bundle.")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "plugin-bundle" / "easyslides")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = build_bundle(args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Built EasySlides plugin bundle: {args.out.resolve()} ({result['file_count']} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
