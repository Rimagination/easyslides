#!/usr/bin/env python3
"""Project facade and package patcher for native PPTX enhancement.

This workflow enhances an existing PPTX without regenerating visible slides.
It appends speaker notes, optional narration audio, auto-advance timings, and
page transitions by patching OOXML package parts directly.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx import Presentation

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pptx_animations import TRANSITIONS, create_transition_xml  # noqa: E402
from svg_to_pptx.pptx_builder import (  # noqa: E402
    _add_default_content_type,
    _append_relationship,
    _ensure_notes_master,
)
from svg_to_pptx.pptx_narration import (  # noqa: E402
    AUDIO_CONTENT_TYPES,
    AUDIO_REL_TYPE,
    IMAGE_REL_TYPE,
    MEDIA_REL_TYPE,
    NARRATION_EXTENSIONS,
    TRANSPARENT_PNG_BYTES,
    apply_recorded_timing,
    inject_narration,
    next_shape_id,
    probe_audio_duration,
)
from svg_to_pptx.pptx_notes import (  # noqa: E402
    create_notes_slide_rels_xml,
    create_notes_slide_xml,
    markdown_to_plain_text,
)


SCHEMA = "native_pptx_enhancement_project.v1"
LEGACY_SCHEMAS = {"native_narration_pptx_project.v1"}
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NOTES_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
NOTES_SLIDE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
)


@dataclass(frozen=True)
class SlidePart:
    index: int
    part_name: str
    slide_number: int


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value).strip("._") or "pptx_enhance"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _project_relative(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)


def _resolve_project_path(project: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project / path


def _extract_pptx(source_pptx: Path, extract_dir: Path) -> None:
    with zipfile.ZipFile(source_pptx, "r") as zf:
        zf.extractall(extract_dir)


def _zip_dir(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir).as_posix())


def _relationship_file_for_part(extract_dir: Path, part_name: str) -> Path:
    part = Path(part_name)
    return extract_dir / part.parent / "_rels" / f"{part.name}.rels"


def _ensure_rels_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{PACKAGE_REL_NS}">\n</Relationships>',
        encoding="utf-8",
    )


def _remove_relationships_by_type(rels_path: Path, rel_type: str) -> None:
    if not rels_path.exists():
        return
    content = rels_path.read_text(encoding="utf-8")
    content = re.sub(
        rf'\s*<Relationship\b[^>]*\bType="{re.escape(rel_type)}"[^>]*/>',
        "",
        content,
    )
    rels_path.write_text(content, encoding="utf-8")


def _target_to_part(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("ppt/"):
        return target
    return f"ppt/{target}"


def _slide_number_from_part(part_name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", part_name)
    if not match:
        raise ValueError(f"Unsupported slide part name: {part_name}")
    return int(match.group(1))


def read_slide_parts(extract_dir: Path) -> list[SlidePart]:
    presentation_path = extract_dir / "ppt" / "presentation.xml"
    rels_path = extract_dir / "ppt" / "_rels" / "presentation.xml.rels"
    if not presentation_path.exists() or not rels_path.exists():
        raise RuntimeError("PPTX package is missing presentation.xml or its relationships")

    rels_root = ET.parse(rels_path).getroot()
    rels: dict[str, str] = {}
    for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rels[rel_id] = target

    presentation_root = ET.parse(presentation_path).getroot()
    slide_parts: list[SlidePart] = []
    for index, slide_id in enumerate(
        presentation_root.findall(f".//{{{PRESENTATION_NS}}}sldId"),
        start=1,
    ):
        rel_id = slide_id.attrib.get(f"{{{REL_NS}}}id")
        if not rel_id or rel_id not in rels:
            continue
        part_name = _target_to_part(rels[rel_id])
        slide_parts.append(
            SlidePart(
                index=index,
                part_name=part_name,
                slide_number=_slide_number_from_part(part_name),
            )
        )
    if not slide_parts:
        raise RuntimeError("No slides found in presentation.xml")
    return slide_parts


def _note_path(notes_dir: Path, index: int) -> Path | None:
    candidates = [
        notes_dir / f"{index:03d}.md",
        notes_dir / f"{index:02d}.md",
        notes_dir / f"{index}.md",
        notes_dir / f"slide_{index:03d}.md",
        notes_dir / f"slide_{index:02d}.md",
        notes_dir / f"slide_{index}.md",
        notes_dir / f"slide{index:03d}.md",
        notes_dir / f"slide{index:02d}.md",
        notes_dir / f"slide{index}.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _audio_path(audio_dir: Path, index: int) -> Path | None:
    stems = [
        f"{index:03d}",
        f"{index:02d}",
        str(index),
        f"slide_{index:03d}",
        f"slide_{index:02d}",
        f"slide_{index}",
        f"slide{index:03d}",
        f"slide{index:02d}",
        f"slide{index}",
    ]
    for stem in stems:
        for ext in NARRATION_EXTENSIONS:
            candidate = audio_dir / f"{stem}{ext}"
            if candidate.is_file():
                return candidate
    return None


def _add_override(content_types: str, part_name: str, content_type: str) -> str:
    if re.search(
        rf'<Override\b[^>]*\bPartName="/{re.escape(part_name)}"[^>]*/>',
        content_types,
    ):
        return content_types
    override = f'  <Override PartName="/{part_name}" ContentType="{content_type}"/>'
    return content_types.replace("</Types>", override + "\n</Types>")


def _set_transition_only(slide_xml: str, effect: str, duration: float) -> str:
    transition_xml = create_transition_xml(effect=effect, duration=duration)
    slide_xml = re.sub(r"\s*<p:transition\b[^>]*/>", "", slide_xml, count=1)
    slide_xml = re.sub(
        r"\s*<p:transition\b[^>]*>.*?</p:transition>",
        "",
        slide_xml,
        count=1,
        flags=re.S,
    )
    if "<p:timing>" in slide_xml:
        return slide_xml.replace("<p:timing>", transition_xml + "\n  <p:timing>", 1)
    return slide_xml.replace("</p:sld>", transition_xml + "\n</p:sld>", 1)


def _apply_recorded_timing_without_transition(slide_xml: str, advance_after: float) -> str:
    adv_ms = max(1, int(advance_after * 1000))
    transition_xml = f'  <p:transition advTm="{adv_ms}"/>'
    slide_xml = re.sub(r"\s*<p:transition\b[^>]*/>", "", slide_xml, count=1)
    slide_xml = re.sub(
        r"\s*<p:transition\b[^>]*>.*?</p:transition>",
        "",
        slide_xml,
        count=1,
        flags=re.S,
    )
    if "<p:timing>" in slide_xml:
        return slide_xml.replace("<p:timing>", transition_xml + "\n  <p:timing>", 1)
    return slide_xml.replace("</p:sld>", transition_xml + "\n</p:sld>", 1)


def _apply_notes(extract_dir: Path, slide: SlidePart, note_md: Path) -> None:
    notes_text = markdown_to_plain_text(note_md.read_text(encoding="utf-8"))
    if not notes_text:
        return

    notes_dir = extract_dir / "ppt" / "notesSlides"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"notesSlide{slide.index}.xml").write_text(
        create_notes_slide_xml(slide.slide_number, notes_text),
        encoding="utf-8",
    )
    notes_rels_dir = notes_dir / "_rels"
    notes_rels_dir.mkdir(parents=True, exist_ok=True)
    (notes_rels_dir / f"notesSlide{slide.index}.xml.rels").write_text(
        create_notes_slide_rels_xml(slide.slide_number),
        encoding="utf-8",
    )

    slide_rels = _relationship_file_for_part(extract_dir, slide.part_name)
    _ensure_rels_file(slide_rels)
    _remove_relationships_by_type(slide_rels, NOTES_REL_TYPE)
    _append_relationship(
        slide_rels,
        NOTES_REL_TYPE,
        f"../notesSlides/notesSlide{slide.index}.xml",
    )


def _apply_audio(
    extract_dir: Path,
    slide: SlidePart,
    audio_path: Path,
    *,
    timings_enabled: bool,
    transition_enabled: bool,
    transition: str,
    transition_duration: float,
    narration_padding: float,
) -> str:
    media_dir = extract_dir / "ppt" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    ext = audio_path.suffix.lower()
    media_name = f"native_enhance_audio_{slide.index:03d}{ext}"
    shutil.copy2(audio_path, media_dir / media_name)

    poster_name = "native_enhance_audio_poster.png"
    poster_path = media_dir / poster_name
    if not poster_path.exists():
        poster_path.write_bytes(TRANSPARENT_PNG_BYTES)

    slide_rels = _relationship_file_for_part(extract_dir, slide.part_name)
    _ensure_rels_file(slide_rels)
    media_rid = _append_relationship(slide_rels, MEDIA_REL_TYPE, f"../media/{media_name}")
    audio_rid = _append_relationship(slide_rels, AUDIO_REL_TYPE, f"../media/{media_name}")
    poster_rid = _append_relationship(slide_rels, IMAGE_REL_TYPE, f"../media/{poster_name}")

    slide_xml_path = extract_dir / slide.part_name
    slide_xml = slide_xml_path.read_text(encoding="utf-8")
    shape_id = next_shape_id(slide_xml)
    slide_xml = inject_narration(
        slide_xml,
        shape_id=shape_id,
        shape_name=media_name,
        audio_rid=audio_rid,
        media_rid=media_rid,
        poster_rid=poster_rid,
    )
    if timings_enabled:
        duration = probe_audio_duration(audio_path)
        if duration is None:
            raise RuntimeError(f"Unable to read narration duration with ffprobe: {audio_path}")
        advance_after = duration + narration_padding
        if transition_enabled and transition != "none":
            slide_xml = apply_recorded_timing(
                slide_xml,
                advance_after=advance_after,
                transition_duration=transition_duration,
                transition_effect=transition,
            )
        else:
            slide_xml = _apply_recorded_timing_without_transition(slide_xml, advance_after)
    elif transition_enabled and transition != "none":
        slide_xml = _set_transition_only(slide_xml, transition, transition_duration)
    slide_xml_path.write_text(slide_xml, encoding="utf-8")
    return ext


def _module_enabled(project_json: dict, plan_data: dict, name: str) -> bool:
    modules = plan_data.get("modules") if isinstance(plan_data, dict) else None
    if isinstance(modules, dict) and isinstance(modules.get(name), dict):
        return modules[name].get("enabled") is True
    project_modules = project_json.get("modules")
    if isinstance(project_modules, dict) and isinstance(project_modules.get(name), dict):
        return project_modules[name].get("enabled") is True
    if isinstance(project_modules, list):
        return name in project_modules
    return name == "notes"


def _plan_path(project: Path) -> Path:
    return project / "analysis" / "enhancement_plan.json"


def _load_plan(project: Path) -> dict:
    path = _plan_path(project)
    return _read_json(path) if path.is_file() else {}


def _notes_audio_dirs(project: Path, project_json: dict) -> tuple[Path, Path, Path]:
    source = _resolve_project_path(project, project_json["source_pptx"])
    notes_dir = _resolve_project_path(project, project_json.get("notes_dir", "notes"))
    audio_dir = _resolve_project_path(project, project_json.get("audio_dir", "audio"))
    exports_dir = _resolve_project_path(project, project_json.get("exports_dir", "exports"))
    return source, notes_dir, audio_dir, exports_dir


def init_project(source_pptx: str | Path, *, name: str | None = None, base_dir: str | Path = "projects") -> Path:
    source = Path(source_pptx)
    if not source.is_file():
        raise FileNotFoundError(f"Source PPTX not found: {source}")
    project_name = _safe_name(name or f"{source.stem}_native_enhance")
    project = Path(base_dir) / project_name
    if project.exists():
        raise FileExistsError(f"Project already exists: {project}")
    for rel in ("sources", "analysis", "notes", "audio", "exports", "validation"):
        (project / rel).mkdir(parents=True, exist_ok=True)
    archived = project / "sources" / source.name
    shutil.copy2(source, archived)
    with tempfile.TemporaryDirectory(prefix="native-enhance-init-") as tmp:
        extract_dir = Path(tmp) / "pptx"
        _extract_pptx(archived, extract_dir)
        slide_parts = read_slide_parts(extract_dir)
    slide_index = {
        "schema": "native_pptx_enhancement_slide_index.v1",
        "source_pptx": _project_relative(archived, project),
        "slide_count": len(slide_parts),
        "slides": [
            {
                "slide": slide.index,
                "note_file": f"notes/{slide.index:03d}.md",
                "audio_stem": f"{slide.index:03d}",
                "partname": slide.part_name,
                "slide_number": slide.slide_number,
            }
            for slide in slide_parts
        ],
    }
    _write_json(project / "analysis" / "slide_index.json", slide_index)
    project_json = {
        "schema": SCHEMA,
        "kind": "native_pptx_enhancement",
        "source_pptx": _project_relative(archived, project),
        "source_original": str(source.resolve()),
        "slide_count": len(slide_parts),
        "notes_dir": "notes",
        "audio_dir": "audio",
        "exports_dir": "exports",
        "modules": {
            "notes": {"enabled": True, "requires_confirmation": True},
            "audio": {"enabled": False},
            "timings": {"enabled": False},
            "transitions": {"enabled": False, "effect": "fade", "duration": 0.5},
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(project / "project.json", project_json)
    plan(project)
    return project


def plan(project_path: str | Path) -> dict:
    project = Path(project_path)
    project_json = _read_json(project / "project.json")
    source, notes_dir, audio_dir, _exports_dir = _notes_audio_dirs(project, project_json)
    with tempfile.TemporaryDirectory(prefix="native-enhance-plan-") as tmp:
        extract_dir = Path(tmp) / "pptx"
        _extract_pptx(source, extract_dir)
        slides = read_slide_parts(extract_dir)
    notes_count = sum(1 for slide in slides if _note_path(notes_dir, slide.index))
    audio_count = sum(1 for slide in slides if _audio_path(audio_dir, slide.index))
    modules = project_json["modules"]
    if isinstance(modules, dict):
        if "notes" in modules:
            modules["notes"]["coverage"] = {"ready": notes_count, "total": len(slides)}
        if "audio" in modules:
            modules["audio"]["coverage"] = {"ready": audio_count, "total": len(slides)}
        if "timings" in modules:
            modules["timings"]["source"] = "audio_duration"
            modules["timings"].setdefault("narration_padding", 0.4)
    plan_data = {
        "schema": "native_pptx_enhancement_plan.v1",
        "status": "draft",
        "source_pptx": project_json["source_pptx"],
        "slide_count": len(slides),
        "modules": modules,
        "notes_policy": "spoken narration only; do not rewrite visible slide content",
        "not_in_v1": [
            "object_animation",
            "visible_watermark",
            "footer_or_logo_insertion",
            "background_music",
            "media_compression",
        ],
    }
    _write_json(project / "analysis" / "enhancement_plan.json", plan_data)
    return plan_data


def validate(project_path: str | Path) -> tuple[list[str], list[str]]:
    project = Path(project_path)
    errors: list[str] = []
    warnings: list[str] = []
    for rel in ("project.json", "analysis/slide_index.json", "analysis/enhancement_plan.json"):
        if not (project / rel).is_file():
            errors.append(f"Missing {rel}")
    if errors:
        return errors, warnings
    project_json = _read_json(project / "project.json")
    if project_json.get("schema") not in {SCHEMA, *LEGACY_SCHEMAS}:
        errors.append(f"project.json schema must be {SCHEMA}")
    source, notes_dir, audio_dir, _exports_dir = _notes_audio_dirs(project, project_json)
    if not source.is_file():
        errors.append(f"Archived source PPTX missing: {source}")
    if errors:
        return errors, warnings
    with tempfile.TemporaryDirectory(prefix="native-enhance-validate-") as tmp:
        extract_dir = Path(tmp) / "pptx"
        _extract_pptx(source, extract_dir)
        slides = read_slide_parts(extract_dir)
    plan_data = _load_plan(project)
    notes_enabled = _module_enabled(project_json, plan_data, "notes")
    audio_enabled = _module_enabled(project_json, plan_data, "audio")
    notes_count = sum(1 for slide in slides if _note_path(notes_dir, slide.index))
    audio_count = sum(1 for slide in slides if _audio_path(audio_dir, slide.index))
    if notes_enabled and notes_count and notes_count != len(slides):
        warnings.append(f"notes enabled but note count {notes_count} != slide count {len(slides)}")
    if audio_enabled and audio_count and audio_count != len(slides):
        warnings.append(f"audio enabled but audio count {audio_count} != slide count {len(slides)}")
    report = {
        "schema": "native_pptx_enhancement_validation.v1",
        "slide_count": len(slides),
        "plan_status": plan_data.get("status") or "missing",
        "enabled_modules": [
            name
            for name in ("notes", "audio", "timings", "transitions")
            if _module_enabled(project_json, plan_data, name)
        ],
        "notes_count": notes_count,
        "audio_count": audio_count,
        "missing_notes": [
            slide.index for slide in slides
            if notes_enabled and _note_path(notes_dir, slide.index) is None
        ],
        "missing_audio": [
            slide.index for slide in slides
            if audio_enabled and _audio_path(audio_dir, slide.index) is None
        ],
    }
    _write_json(project / "validation" / "report.json", report)
    return errors, warnings


def apply(
    project_path: str | Path,
    *,
    output: str | Path | None = None,
    overwrite: bool = False,
    force: bool = False,
    transition: str | None = None,
    transition_duration: float | None = None,
    narration_padding: float | None = None,
    apply_transition_without_audio: bool = False,
) -> Path:
    project = Path(project_path)
    project_json = _read_json(project / "project.json")
    if project_json.get("schema") not in {SCHEMA, *LEGACY_SCHEMAS}:
        raise ValueError(f"not a native PPTX enhancement project: {project}")
    plan_data = _load_plan(project)
    if plan_data.get("status") != "confirmed" and not force:
        raise RuntimeError(
            f"enhancement plan is not confirmed: {_plan_path(project)} "
            '(set status to "confirmed" or pass --force)'
        )

    source, notes_dir, audio_dir, exports_dir = _notes_audio_dirs(project, project_json)
    output_path = (
        Path(output)
        if output is not None
        else exports_dir / f"{source.stem}_enhanced.pptx"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output already exists, pass --overwrite: {output_path}")

    transitions_cfg = {}
    timings_cfg = {}
    if isinstance(plan_data.get("modules"), dict):
        transitions_cfg = plan_data["modules"].get("transitions", {}) or {}
        timings_cfg = plan_data["modules"].get("timings", {}) or {}
    project_transitions_cfg = {}
    if isinstance(project_json.get("modules"), dict):
        project_transitions_cfg = project_json["modules"].get("transitions", {}) or {}
    transition_effect = (
        transition
        or transitions_cfg.get("effect")
        or project_transitions_cfg.get("effect")
        or "fade"
    )
    transition_seconds = float(
        transition_duration
        if transition_duration is not None
        else transitions_cfg.get("duration", project_transitions_cfg.get("duration", 0.5))
    )
    padding_seconds = float(
        narration_padding
        if narration_padding is not None
        else timings_cfg.get("narration_padding", 0.4)
    )

    notes_enabled = _module_enabled(project_json, plan_data, "notes")
    audio_enabled = _module_enabled(project_json, plan_data, "audio")
    timings_enabled = _module_enabled(project_json, plan_data, "timings")
    transitions_enabled = _module_enabled(project_json, plan_data, "transitions")
    apply_transition_without_audio = (
        apply_transition_without_audio
        or bool(transitions_cfg.get("apply_without_audio"))
        or bool(project_transitions_cfg.get("apply_without_audio"))
    )

    with tempfile.TemporaryDirectory(prefix="native-enhance-apply-") as tmp:
        extract_dir = Path(tmp) / "pptx"
        _extract_pptx(source, extract_dir)
        slides = read_slide_parts(extract_dir)

        note_indices: set[int] = set()
        audio_exts: set[str] = set()
        audio_count = 0
        transition_only_count = 0
        for slide in slides:
            note = _note_path(notes_dir, slide.index)
            if notes_enabled and note:
                _apply_notes(extract_dir, slide, note)
                note_indices.add(slide.index)

            audio = _audio_path(audio_dir, slide.index)
            if audio_enabled and audio:
                audio_exts.add(
                    _apply_audio(
                        extract_dir,
                        slide,
                        audio,
                        timings_enabled=timings_enabled,
                        transition_enabled=transitions_enabled,
                        transition=transition_effect,
                        transition_duration=transition_seconds,
                        narration_padding=padding_seconds,
                    )
                )
                audio_count += 1
                continue

            if transitions_enabled and apply_transition_without_audio and transition_effect != "none":
                slide_xml_path = extract_dir / slide.part_name
                slide_xml = slide_xml_path.read_text(encoding="utf-8")
                slide_xml_path.write_text(
                    _set_transition_only(slide_xml, transition_effect, transition_seconds),
                    encoding="utf-8",
                )
                transition_only_count += 1

        content_types_path = extract_dir / "[Content_Types].xml"
        content_types = content_types_path.read_text(encoding="utf-8")
        if note_indices:
            content_types = _ensure_notes_master(extract_dir, content_types)
            for index in sorted(note_indices):
                content_types = _add_override(
                    content_types,
                    f"ppt/notesSlides/notesSlide{index}.xml",
                    NOTES_SLIDE_CONTENT_TYPE,
                )
        for ext in sorted(audio_exts):
            content_type = AUDIO_CONTENT_TYPES.get(ext)
            if content_type:
                content_types = _add_default_content_type(content_types, ext, content_type)
        if audio_exts:
            content_types = _add_default_content_type(content_types, "png", "image/png")
        content_types_path.write_text(content_types, encoding="utf-8")

        _zip_dir(extract_dir, output_path)

    report = {
        "schema": "native_pptx_enhancement_apply_report.v1",
        "output": str(output_path),
        "notes_applied": len(note_indices),
        "audio_embedded": audio_count,
        "transition_only_slides": transition_only_count,
    }
    _write_json(project / "validation" / "apply_report.json", report)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native append-only enhancement for existing PPTX files")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="Create a native enhancement project")
    init.add_argument("source_pptx")
    init.add_argument("--name")
    init.add_argument("--dir", default="projects")
    plan_cmd = subparsers.add_parser("plan", help="Refresh enhancement_plan.json")
    plan_cmd.add_argument("project")
    validate_cmd = subparsers.add_parser("validate", help="Validate project artifacts")
    validate_cmd.add_argument("project")
    validate_cmd.add_argument("--json", action="store_true")
    apply_cmd = subparsers.add_parser("apply", help="Apply native package patches")
    apply_cmd.add_argument("project")
    apply_cmd.add_argument("-o", "--output")
    apply_cmd.add_argument("--overwrite", action="store_true")
    apply_cmd.add_argument("--force", action="store_true")
    apply_cmd.add_argument("--transition", choices=sorted(TRANSITIONS.keys()) + ["none"])
    apply_cmd.add_argument("--transition-duration", type=float)
    apply_cmd.add_argument("--narration-padding", type=float)
    apply_cmd.add_argument("--apply-transition-without-audio", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            project = init_project(args.source_pptx, name=args.name, base_dir=args.dir)
            print(f"[OK] Initialized native enhancement project: {project}")
            return 0
        if args.command == "plan":
            plan(args.project)
            print(f"[OK] Wrote enhancement plan: {Path(args.project) / 'analysis' / 'enhancement_plan.json'}")
            return 0
        if args.command == "validate":
            errors, warnings = validate(args.project)
            if args.json:
                print(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
            else:
                for warning in warnings:
                    print(f"[WARN] {warning}")
                for error in errors:
                    print(f"[ERROR] {error}")
                if not errors:
                    print("[OK] Native enhancement project is valid")
            return 0 if not errors else 1
        if args.command == "apply":
            output = apply(
                args.project,
                output=args.output,
                overwrite=args.overwrite,
                force=args.force,
                transition=args.transition,
                transition_duration=args.transition_duration,
                narration_padding=args.narration_padding,
                apply_transition_without_audio=args.apply_transition_without_audio,
            )
            print(f"[OK] Wrote enhanced PPTX: {output}")
            return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
