#!/usr/bin/env python3
"""PPT Master-style image acquisition orchestration for EasySlides.

This module deliberately sits above ``image_gen.py``.  The existing image
generator owns provider-specific API calls; this module owns the durable
resource contract, deterministic path selection, host-native handoff, status
reconciliation, and optional cover/ending bindings consumed by Slide IR.

The host-native path is intentionally represented as a request artifact.  A
Codex/agent host can read that artifact, invoke its native image tool, place
the result under ``images/``, and then run ``reconcile``.  The repository CLI
must not guess how a host exposes a native tool.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:  # Direct script execution from scripts/.
    from config import load_prefixed_env_file
    from image_gen import (
        STATUS_FAILED,
        STATUS_GENERATED,
        STATUS_NEEDS_MANUAL,
        STATUS_PENDING,
        VALID_STATUSES,
        load_manifest,
        render_manifest_md_to_file,
        save_manifest,
    )
except ImportError:  # pragma: no cover - package-style imports in tests/tools.
    from scripts.config import load_prefixed_env_file
    from scripts.image_gen import (
        STATUS_FAILED,
        STATUS_GENERATED,
        STATUS_NEEDS_MANUAL,
        STATUS_PENDING,
        VALID_STATUSES,
        load_manifest,
        render_manifest_md_to_file,
        save_manifest,
    )

try:
    from scripts.theme_tokens import DEFAULT_TOKENS, resolve_template_tokens
except ImportError:  # pragma: no cover - direct script execution.
    from theme_tokens import DEFAULT_TOKENS, resolve_template_tokens


SCHEMA = "easyslides.image_resources.v1"
CAPABILITY_SCHEMA = "easyslides.image_capability.v1"
PATH_AUTO = "auto"
PATH_API = "api"
PATH_HOST_NATIVE = "host-native"
PATH_MANUAL = "manual"
VALID_PATHS = {PATH_AUTO, PATH_API, PATH_HOST_NATIVE, PATH_MANUAL}
VALID_PAGE_ROLES = {"local", "hero_page"}
VALID_TEXT_POLICIES = {"none", "embedded"}
VALID_ASSET_ROLES = {"background", "illustration", "decorative"}
HERO_SLIDE_ROLES = {"cover", "ending", "chapter", "transition"}
RETRYABLE_STATUSES = {STATUS_PENDING, STATUS_FAILED}


class ImageAcquisitionError(ValueError):
    """Raised when an image resource contract cannot be resolved safely."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def detect_imagegen_skill(environment: Mapping[str, str] | None = None) -> Path | None:
    """Locate the host-provided imagegen skill without hard-coding a secret."""
    env = dict(os.environ if environment is None else environment)
    explicit = str(env.get("EASYSLIDES_IMAGEGEN_SKILL") or "").strip()
    candidates = [Path(explicit)] if explicit else []
    codex_home = str(env.get("CODEX_HOME") or "").strip()
    if codex_home:
        candidates.append(Path(codex_home) / "skills" / ".system" / "imagegen" / "SKILL.md")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def detect_imagegen_capability(
    environment: Mapping[str, str] | None = None,
    *,
    host_native_override: bool | None = None,
) -> dict[str, Any]:
    """Return one normalized capability record for all image providers.

    The repository cannot invoke a Codex skill itself.  It can, however,
    expose a stable host handoff when the skill is installed.  Keeping API,
    host-native, and manual states in one record prevents each workflow from
    reimplementing slightly different detection rules.
    """
    env = dict(os.environ if environment is None else environment)
    skill_path = detect_imagegen_skill(env)
    api_backend = str(env.get("IMAGE_BACKEND") or "").strip()
    configured_host = _truthy(env.get("EASYSLIDES_HOST_IMAGEGEN"))
    if host_native_override is None:
        host_native = configured_host
    else:
        host_native = bool(host_native_override)
    if api_backend:
        mode = PATH_API
        reason = "image_backend_configured"
    elif host_native:
        mode = PATH_HOST_NATIVE
        reason = "host_native_declared"
    else:
        mode = PATH_MANUAL
        reason = "no_api_or_host_native_capability"
    return {
        "schema_version": CAPABILITY_SCHEMA,
        "available": bool(api_backend or host_native),
        "mode": mode,
        "reason": reason,
        "api_configured": bool(api_backend),
        "backend": api_backend or None,
        "host_native_available": host_native,
        "imagegen_skill_available": skill_path is not None,
        "imagegen_skill": str(skill_path or ""),
        "fallback_order": [PATH_API, PATH_HOST_NATIVE, PATH_MANUAL],
        "fallback": "template_shell",
    }


def _load_image_env() -> None:
    """Load only capability-routing keys from the repository/user .env."""
    load_prefixed_env_file(("IMAGE_BACKEND", "EASYSLIDES_"))


def _safe_relative_filename(filename: str) -> str:
    """Validate a manifest filename without allowing output-directory escape."""
    candidate = Path(filename)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ImageAcquisitionError(
            f"manifest filename must stay below the output directory: {filename!r}"
        )
    if not str(filename).strip() or candidate.name in {"", "."}:
        raise ImageAcquisitionError("manifest filename must be a non-empty relative path")
    return str(candidate)


def validate_image_manifest(data: Mapping[str, Any], *, source: str = "manifest") -> dict[str, Any]:
    """Validate the shared image resource contract and return a copy.

    The lower-level ``image_gen.py`` validator remains authoritative for its
    legacy fields.  This layer adds the PPTMaster-style routing metadata while
    keeping old manifests readable.
    """
    if not isinstance(data, Mapping):
        raise ImageAcquisitionError(f"{source}: top level must be a JSON object")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ImageAcquisitionError(f"{source}: 'items' must be a non-empty array")

    acquisition = data.get("acquisition") or {}
    if not isinstance(acquisition, Mapping):
        raise ImageAcquisitionError(f"{source}: 'acquisition' must be an object")
    path = str(acquisition.get("path") or PATH_AUTO).strip().lower()
    if path not in VALID_PATHS:
        raise ImageAcquisitionError(
            f"{source}: acquisition.path must be one of {sorted(VALID_PATHS)}"
        )

    seen: set[str] = set()
    normalized = deepcopy(dict(data))
    normalized["schema_version"] = str(data.get("schema_version") or SCHEMA)
    normalized["acquisition"] = dict(acquisition)
    normalized["acquisition"]["path"] = path
    normalized_items: list[dict[str, Any]] = []

    for index, raw_item in enumerate(items):
        prefix = f"{source}: items[{index}]"
        if not isinstance(raw_item, Mapping):
            raise ImageAcquisitionError(f"{prefix} must be an object")
        item = dict(raw_item)
        for field in ("filename", "prompt", "aspect_ratio", "status"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ImageAcquisitionError(f"{prefix}.{field} must be a non-empty string")
        item["filename"] = _safe_relative_filename(item["filename"])
        if item["filename"] in seen:
            raise ImageAcquisitionError(f"{prefix}: duplicate filename {item['filename']!r}")
        seen.add(item["filename"])
        if item["status"] not in VALID_STATUSES:
            raise ImageAcquisitionError(
                f"{prefix}.status must be one of {sorted(VALID_STATUSES)}"
            )

        page_role = str(item.get("page_role") or "local").strip().lower()
        if page_role not in VALID_PAGE_ROLES:
            raise ImageAcquisitionError(
                f"{prefix}.page_role must be one of {sorted(VALID_PAGE_ROLES)}"
            )
        text_policy = str(item.get("text_policy") or "none").strip().lower()
        if text_policy not in VALID_TEXT_POLICIES:
            raise ImageAcquisitionError(
                f"{prefix}.text_policy must be one of {sorted(VALID_TEXT_POLICIES)}"
            )
        item["page_role"] = page_role
        item["text_policy"] = text_policy
        if data.get("purpose") == "slide_reconstruction" and text_policy != "embedded":
            raise ImageAcquisitionError(f"{prefix}: full slides require text_policy=embedded")

        default_asset_role = "background" if page_role == "hero_page" else "illustration"
        asset_role = str(item.get("asset_role") or default_asset_role).strip().lower()
        if asset_role not in VALID_ASSET_ROLES:
            raise ImageAcquisitionError(
                f"{prefix}.asset_role must be one of {sorted(VALID_ASSET_ROLES)}"
            )
        item["asset_role"] = asset_role
        placement = item.get("placement")
        if placement is not None and not isinstance(placement, Mapping):
            raise ImageAcquisitionError(f"{prefix}.placement must be an object")
        if isinstance(placement, Mapping):
            normalized_placement = dict(placement)
            frame = normalized_placement.get("frame")
            if frame is not None:
                if not isinstance(frame, Mapping):
                    raise ImageAcquisitionError(f"{prefix}.placement.frame must be an object")
                for coordinate in ("x", "y", "width", "height"):
                    if coordinate not in frame:
                        raise ImageAcquisitionError(
                            f"{prefix}.placement.frame.{coordinate} is required"
                        )
                    try:
                        if coordinate in {"width", "height"} and float(frame[coordinate]) <= 0:
                            raise ValueError
                        float(frame[coordinate])
                    except (TypeError, ValueError) as exc:
                        raise ImageAcquisitionError(
                            f"{prefix}.placement.frame.{coordinate} must be numeric"
                        ) from exc
                normalized_placement["frame"] = dict(frame)
            item["placement"] = normalized_placement

        slide_role = str(item.get("slide_role") or "").strip().lower()
        if slide_role and slide_role not in {"cover", "ending", "chapter", "transition", "content"}:
            raise ImageAcquisitionError(
                f"{prefix}.slide_role must be cover, ending, chapter, transition, or content"
            )
        if slide_role:
            item["slide_role"] = slide_role
        if "id" not in item or not str(item.get("id") or "").strip():
            item["id"] = Path(item["filename"]).stem
        normalized_items.append(item)

    normalized["items"] = normalized_items
    if data.get("purpose") == "slide_reconstruction":
        if not isinstance(data.get("reference_image"), str) or not data["reference_image"].strip():
            raise ImageAcquisitionError("slide reconstruction requires reference_image")
        if path != PATH_HOST_NATIVE:
            raise ImageAcquisitionError("full-slide ImageGen requests require acquisition.path=host-native")
        ids = [item['id'] for item in normalized_items]
        if len(set(ids)) != len(ids):
            raise ImageAcquisitionError("full-slide item ids must be unique")
    return normalized


def load_image_resource_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a shared image resource manifest."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ImageAcquisitionError(f"image manifest not found: {manifest_path}")
    try:
        # Reuse image_gen's legacy validation first.  It provides the same
        # error semantics for existing image_prompts.json files.
        data = load_manifest(str(manifest_path))
    except ValueError as exc:
        raise ImageAcquisitionError(str(exc)) from exc
    return validate_image_manifest(data, source=str(manifest_path))


def output_path_for_item(
    manifest_path: str | Path,
    item: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
) -> Path:
    """Return a safe output path for one manifest item."""
    manifest = Path(manifest_path).resolve()
    root = Path(output_dir).resolve() if output_dir else manifest.parent
    filename = _safe_relative_filename(str(item.get("filename") or ""))
    output = (root / filename).resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:  # defensive check for platform-specific paths
        raise ImageAcquisitionError(f"output path escapes image directory: {output}") from exc
    return output


def reconcile_manifest(
    manifest_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Reconcile status with files on disk using evidence-driven transitions."""
    manifest = load_image_resource_manifest(manifest_path)
    if manifest.get('purpose') == 'slide_reconstruction' and output_dir and Path(output_dir).resolve() != Path(manifest_path).resolve().parent:
        raise ImageAcquisitionError('Place the full-slide manifest beside its generated outputs; alternate output directories are unsupported')
    changed = False
    for item in manifest["items"]:
        output = output_path_for_item(manifest_path, item, output_dir=output_dir)
        exists = output.is_file()
        status = item["status"]
        if manifest.get('purpose') == 'slide_reconstruction':
            try:
                from scripts.image_generation_contract import validate_result
            except ModuleNotFoundError:
                from image_generation_contract import validate_result
            try:
                validate_result(manifest_path, manifest, item, output)
                item['status'] = STATUS_GENERATED
                item.pop('last_error', None)
            except (ValueError, OSError) as exc:
                item['status'] = STATUS_FAILED if status == STATUS_GENERATED else status
                item['last_error'] = str(exc)
            changed = True
            continue
        if exists and status != STATUS_GENERATED:
            item["status"] = STATUS_GENERATED
            item.pop("last_error", None)
            changed = True
        elif status == STATUS_GENERATED and not exists:
            item["status"] = STATUS_FAILED
            item["last_error"] = f"Generated file is missing: {output}"
            changed = True
    if write and changed:
        save_manifest(str(manifest_path), manifest)
    return {
        "schema_version": SCHEMA,
        "status": "pass",
        "manifest": str(Path(manifest_path).resolve()),
        "changed": changed,
        "items": manifest["items"],
    }


def resolve_acquisition_path(
    manifest: Mapping[str, Any] | None = None,
    *,
    explicit_path: str | None = None,
    host_native_available: bool | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Choose API, host-native, or manual acquisition deterministically.

    Explicit path choices win.  Otherwise an ``IMAGE_BACKEND`` wins over a
    host-native capability, matching PPTMaster's default A → B → C chain.
    """
    env = dict(os.environ if environment is None else environment)
    requested = explicit_path
    if requested is None and manifest:
        acquisition = manifest.get("acquisition") or {}
        if isinstance(acquisition, Mapping):
            requested = acquisition.get("path")
    requested = str(requested or PATH_AUTO).strip().lower()
    if requested not in VALID_PATHS:
        raise ImageAcquisitionError(
            f"acquisition path must be one of {sorted(VALID_PATHS)}"
        )

    capability = detect_imagegen_capability(env, host_native_override=host_native_available)
    api_configured = bool(capability["api_configured"])
    if requested == PATH_API:
        selected, reason = PATH_API, "explicit_api_path"
    elif requested == PATH_HOST_NATIVE:
        selected, reason = PATH_HOST_NATIVE, "explicit_host_native_path"
    elif requested == PATH_MANUAL:
        selected, reason = PATH_MANUAL, "explicit_manual_path"
    elif api_configured:
        selected, reason = PATH_API, "image_backend_configured"
    else:
        host_native_available = bool(capability["host_native_available"])
        if host_native_available:
            selected, reason = PATH_HOST_NATIVE, str(capability["reason"])
        else:
            selected, reason = PATH_MANUAL, "no_api_or_host_native_capability"

    return {
        "schema_version": SCHEMA,
        "path": selected,
        "reason": reason,
        "requested_path": requested,
        "image_backend_configured": api_configured,
        "host_native_available": bool(host_native_available),
        "imagegen_skill": str(capability["imagegen_skill"] or ""),
        "capability": capability,
        "fallback_order": [PATH_API, PATH_HOST_NATIVE, PATH_MANUAL],
    }


def _item_matches_role(item: Mapping[str, Any], slide_role: str) -> bool:
    declared_role = str(item.get("slide_role") or "").strip().lower()
    if declared_role:
        return declared_role == slide_role
    purpose = str(item.get("purpose") or "").lower()
    return slide_role in purpose or slide_role == "cover" and "title" in purpose


def select_hero_item(
    manifest: Mapping[str, Any],
    slide_role: str,
    *,
    resource_id: str | None = None,
) -> dict[str, Any] | None:
    """Select the explicit or inferred hero resource for cover/ending."""
    role = str(slide_role or "").strip().lower()
    if role not in HERO_SLIDE_ROLES:
        return None
    items = [item for item in manifest.get("items", []) if isinstance(item, Mapping)]
    if resource_id:
        for item in items:
            if str(item.get("id") or "") == resource_id or str(item.get("filename") or "") == resource_id:
                return dict(item)
        raise ImageAcquisitionError(f"image resource not found: {resource_id}")
    candidates = [
        item
        for item in items
        if str(item.get("page_role") or "local") == "hero_page"
        and _item_matches_role(item, role)
    ]
    return dict(candidates[0]) if candidates else None


def resolve_background_binding(
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
    slide_role: str,
    *,
    output_dir: str | Path | None = None,
    resource_id: str | None = None,
) -> dict[str, Any] | None:
    """Resolve a generated hero item into a renderer-ready background binding."""
    item = select_hero_item(manifest, slide_role, resource_id=resource_id)
    if item is None:
        return None
    return resolve_image_binding(
        manifest_path,
        manifest,
        item,
        output_dir=output_dir,
        placement_override=None,
    )


def resolve_image_binding(
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
    item: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    placement_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve any generated manifest item into a renderer-ready image binding."""
    output = output_path_for_item(manifest_path, item, output_dir=output_dir)
    page_role = str(item.get("page_role") or "local")
    asset_role = str(item.get("asset_role") or ("background" if page_role == "hero_page" else "illustration"))
    placement = dict(item.get("placement") or {}) if isinstance(item.get("placement"), Mapping) else {}
    if isinstance(placement_override, Mapping):
        placement.update(dict(placement_override))
    binding: dict[str, Any] = {
        "schema_version": SCHEMA,
        "resource_id": str(item.get("id") or Path(str(item["filename"])).stem),
        "filename": str(item["filename"]),
        "slide_role": str(item.get("slide_role") or ""),
        "page_role": page_role,
        "asset_role": asset_role,
        "placement": placement,
        "status": str(item.get("status") or STATUS_PENDING),
        "fallback": "template_shell",
    }
    for key in ("source_policy", "visual_use", "page"):
        if item.get(key) not in (None, ""):
            binding[key] = item[key]
    if item.get("status") != STATUS_GENERATED or not output.is_file():
        return binding
    background = item.get("background") or {}
    if not isinstance(background, Mapping):
        background = {}
    binding.update({"status": STATUS_GENERATED, "path": str(output)})
    if asset_role == "background":
        deck_palette = manifest.get("deck_palette") if isinstance(manifest.get("deck_palette"), Mapping) else manifest.get("theme_tokens")
        if not isinstance(deck_palette, Mapping):
            deck_palette = {}
        binding.update(
            {
                "fit": str(background.get("fit") or placement.get("fit") or "slice"),
                "scrim_fill": str(background.get("scrim_fill") or "#FFFFFF"),
                "scrim_opacity": float(background.get("scrim_opacity", 0.18)),
                "text_tone": str(background.get("text_tone") or "auto"),
                "contrast_target": float(background.get("contrast_target", 4.5)),
                "safe_area": dict(item.get("safe_area") or background.get("safe_area") or {}),
                "text_on_light": str(deck_palette.get("text_on_light") or "#18212B"),
                "text_on_dark": str(deck_palette.get("text_on_dark") or "#FFFFFF"),
            }
        )
        for key in ("readability_mode", "text_color"):
            if background.get(key) not in (None, ""):
                binding[key] = background[key]
    elif placement:
        binding["text_tone"] = str(placement.get("text_tone") or "auto")
        binding["contrast_target"] = float(placement.get("contrast_target", 4.5))
    return binding


def apply_manifest_to_slide_ir(
    slide_ir: dict[str, Any],
    manifest_path: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Attach optional background and local image bindings to Slide IR."""
    if load_image_resource_manifest(manifest_path).get('purpose') == 'slide_reconstruction':
        raise ImageAcquisitionError('Full slide images must enter image-reconstruct; direct background binding is forbidden')
    image_root = Path(output_dir).resolve() if output_dir else Path(manifest_path).resolve().parent
    # Reconcile before binding so a host-native tool can simply place a file
    # and resume compilation; a stale Pending status must not hide valid work.
    reconcile_manifest(manifest_path, output_dir=image_root, write=True)
    manifest = load_image_resource_manifest(manifest_path)
    bound = 0
    pending = 0
    bound_backgrounds = 0
    pending_backgrounds = 0
    for slide in slide_ir.get("slides", []):
        if not isinstance(slide, dict):
            continue
        role = str(slide.get("role") or "").strip().lower()
        explicit_bindings = slide.get("image_bindings")
        requested: list[tuple[str, Mapping[str, Any] | None]] = []
        if isinstance(explicit_bindings, list):
            for raw_binding in explicit_bindings:
                if isinstance(raw_binding, Mapping):
                    resource_id = str(
                        raw_binding.get("resource_id") or raw_binding.get("id") or ""
                    ).strip()
                    if resource_id:
                        override = raw_binding.get("placement")
                        requested.append(
                            (resource_id, override if isinstance(override, Mapping) else None)
                        )
        if not requested:
            resource_id = str(slide.get("image_resource_id") or "").strip()
            if resource_id:
                requested.append((resource_id, None))
            elif role in HERO_SLIDE_ROLES:
                hero = select_hero_item(manifest, role, resource_id=None)
                if hero is not None:
                    requested.append((str(hero.get("id") or hero.get("filename")), None))

        bindings: list[dict[str, Any]] = []
        for resource_id, placement_override in requested:
            item = next(
                (
                    candidate
                    for candidate in manifest.get("items", [])
                    if isinstance(candidate, Mapping)
                    and (
                        str(candidate.get("id") or "") == resource_id
                        or str(candidate.get("filename") or "") == resource_id
                    )
                ),
                None,
            )
            if item is None:
                raise ImageAcquisitionError(f"image resource not found: {resource_id}")
            binding = resolve_image_binding(
                manifest_path,
                manifest,
                item,
                output_dir=image_root,
                placement_override=placement_override,
            )
            bindings.append(binding)
            if binding.get("status") == STATUS_GENERATED and binding.get("path"):
                bound += 1
                if binding.get("asset_role") == "background":
                    bound_backgrounds += 1
            else:
                pending += 1
                if binding.get("asset_role") == "background":
                    pending_backgrounds += 1
        if bindings:
            slide["image_assets"] = bindings
            background = next(
                (binding for binding in bindings if binding.get("asset_role") == "background"),
                None,
            )
            if background is not None:
                slide["background_asset"] = background
            pending_ids = [
                str(binding.get("resource_id") or "")
                for binding in bindings
                if binding.get("status") != STATUS_GENERATED or not binding.get("path")
            ]
            if pending_ids:
                slide["image_fallback"] = {
                    "mode": "template_shell",
                    "pending_resource_ids": pending_ids,
                }
    report = {
        "schema_version": SCHEMA,
        "status": "pass",
        "manifest": str(Path(manifest_path).resolve()),
        "bound_assets": bound,
        "pending_assets": pending,
        "bound_backgrounds": bound_backgrounds,
        "pending_backgrounds": pending_backgrounds,
        "fallback": "template_shell",
        "pending_resource_ids": [
            str(binding.get("resource_id") or "")
            for slide in slide_ir.get("slides", [])
            if isinstance(slide, dict)
            for binding in slide.get("image_assets", [])
            if isinstance(binding, Mapping)
            and (binding.get("status") != STATUS_GENERATED or not binding.get("path"))
        ],
    }
    slide_ir["image_resources"] = report
    return report


def write_host_native_request(
    manifest_path: str | Path,
    manifest: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    request_path: str | Path | None = None,
) -> Path:
    """Write a durable handoff for a host-native image tool."""
    manifest = validate_image_manifest(manifest)
    root = Path(output_dir).resolve() if output_dir else Path(manifest_path).resolve().parent
    pending = []
    for item in manifest.get("items", []):
        if not isinstance(item, Mapping) or item.get("status") not in RETRYABLE_STATUSES:
            continue
        pending.append(
            {
                "id": str(item.get("id") or Path(str(item["filename"])).stem),
                "page": str(item.get("page") or ""),
                "filename": str(item["filename"]),
                "output_path": str(output_path_for_item(manifest_path, item, output_dir=root)),
                "prompt": str(item["prompt"]),
                "aspect_ratio": str(item["aspect_ratio"]),
                "image_size": str(item.get("image_size") or "1K"),
                "page_role": str(item.get("page_role") or "local"),
                "slide_role": str(item.get("slide_role") or ""),
                "text_policy": str(item.get("text_policy") or "none"),
                "asset_role": str(item.get("asset_role") or "illustration"),
                "visual_use": str(item.get("visual_use") or ""),
                "source_policy": str(item.get("source_policy") or ""),
                "safe_area": dict(item.get("safe_area") or {}),
            }
        )
        if manifest.get('purpose') == 'slide_reconstruction':
            try:
                from scripts.image_generation_contract import tool_arguments, fingerprint
            except ModuleNotFoundError:
                from image_generation_contract import tool_arguments, fingerprint
            pending[-1]['tool_arguments'] = tool_arguments(manifest_path, manifest, item)
            pending[-1]['reference_identities'] = [fingerprint(p) for p in pending[-1]['tool_arguments']['referenced_image_paths']]
            pending[-1]['output_kind'] = 'complete_slide_image'
            pending[-1]['next_route'] = 'slide-image-to-editable-pptx'
    target = Path(request_path).resolve() if request_path else Path(manifest_path).with_name("image_acquisition_request.json")
    target.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA,
                "path": PATH_HOST_NATIVE,
                "manifest": str(Path(manifest_path).resolve()),
                "output_dir": str(root),
                "items": pending,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def scaffold_hero_manifest(
    manifest_path: str | Path,
    *,
    topic: str,
    project: str | None = None,
    rendering: str = "vector-illustration",
    palette: str = "cool-corporate",
    primary: str | None = None,
    secondary: str | None = None,
    accent: str | None = None,
    template_dir: str | Path | None = None,
    palette_id: str | None = None,
) -> Path:
    """Create a minimal cover/ending hero manifest for a new deck."""
    target = Path(manifest_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    topic_text = str(topic).strip()
    if not topic_text:
        raise ImageAcquisitionError("topic must be non-empty")
    theme_tokens = dict(DEFAULT_TOKENS)
    selected_palette = str(palette_id or palette or "").strip()
    if template_dir:
        try:
            resolved_theme = resolve_template_tokens(template_dir, palette_id)
        except (OSError, ValueError) as exc:
            raise ImageAcquisitionError(f"cannot resolve template theme: {exc}") from exc
        theme_tokens.update(resolved_theme.get("tokens") or {})
        selected_palette = str(resolved_theme.get("palette_id") or selected_palette)
    primary = str(primary or theme_tokens.get("primary") or "#1E3A5F")
    secondary = str(secondary or theme_tokens.get("surface") or "#F8F9FA")
    accent = str(accent or theme_tokens.get("accent") or "#D4AF37")
    shared = (
        f"Create a quiet 16:9 presentation atmosphere for the topic: {topic_text}. "
        "Use a restrained academic visual language with soft abstract forms, subtle depth, "
        "clear negative space for editable slide text, and no dominant central subject. "
        f"Use the deck palette with primary {primary}, secondary {secondary}, and sparse accent {accent}. "
        "The image is a background layer, not an infographic. No text, letters, numbers, logos, "
        "watermarks, labels, UI, or identifiable brands anywhere in the image."
    )
    data = {
        "schema_version": SCHEMA,
        "project": project or target.parent.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acquisition": {"path": PATH_AUTO},
        "deck_rendering": rendering,
        "deck_palette": selected_palette,
        "theme_tokens": theme_tokens,
        "color_scheme": {"primary": primary, "secondary": secondary, "accent": accent},
        "items": [
            {
                "id": "cover_background",
                "filename": "cover_bg.png",
                "purpose": "Cover background",
                "slide_role": "cover",
                "page_role": "hero_page",
                "text_policy": "none",
                "aspect_ratio": "16:9",
                "image_size": "2K",
                "prompt": shared + " Leave the center and lower third especially calm for the title and presenter metadata.",
                "alt_text": f"Quiet abstract background for {topic_text}",
                "safe_area": {"side": "center", "box": {"x": 180, "y": 245, "width": 920, "height": 260}},
                "background": {
                    "fit": "slice",
                    "text_tone": "auto",
                    "contrast_target": 4.5,
                    "scrim_fill": "#FFFFFF",
                    "scrim_opacity": 0.2,
                },
                "status": STATUS_PENDING,
            },
            {
                "id": "ending_background",
                "filename": "ending_bg.png",
                "purpose": "Ending background",
                "slide_role": "ending",
                "page_role": "hero_page",
                "text_policy": "none",
                "aspect_ratio": "16:9",
                "image_size": "2K",
                "prompt": shared + " Keep the center and upper third open for a short closing line; make the mood slightly more spacious and reflective than the cover.",
                "alt_text": f"Quiet reflective ending background for {topic_text}",
                "safe_area": {"side": "center", "box": {"x": 180, "y": 220, "width": 920, "height": 300}},
                "background": {
                    "fit": "slice",
                    "text_tone": "auto",
                    "contrast_target": 4.5,
                    "scrim_fill": "#FFFFFF",
                    "scrim_opacity": 0.24,
                },
                "status": STATUS_PENDING,
            },
        ],
    }
    normalized = validate_image_manifest(data, source=str(target))
    save_manifest(str(target), normalized)
    render_manifest_md_to_file(str(target), normalized)
    return target


def _run_api_generation(manifest_path: Path, output_dir: Path) -> int:
    """Delegate provider execution to the existing image_gen.py CLI."""
    script = Path(__file__).resolve().with_name("image_gen.py")
    result = subprocess.run(
        [sys.executable, str(script), "--manifest", str(manifest_path), "--output", str(output_dir)],
        cwd=str(script.parent.parent),
        check=False,
    )
    return int(result.returncode)


def prepare_acquisition(
    manifest_path: str | Path,
    *,
    explicit_path: str | None = None,
    host_native_available: bool | None = None,
    output_dir: str | Path | None = None,
    request_path: str | Path | None = None,
    execute_api: bool = False,
) -> dict[str, Any]:
    """Resolve a manifest and prepare or execute its selected acquisition path."""
    manifest_path = Path(manifest_path).resolve()
    output_root = Path(output_dir).resolve() if output_dir else manifest_path.parent
    manifest = load_image_resource_manifest(manifest_path)
    reconciliation = reconcile_manifest(manifest_path, output_dir=output_root, write=True)
    manifest = load_image_resource_manifest(manifest_path)
    resolution = resolve_acquisition_path(
        manifest,
        explicit_path=explicit_path,
        host_native_available=host_native_available,
    )
    if manifest.get('purpose') == 'slide_reconstruction' and resolution['path'] != PATH_HOST_NATIVE:
        raise ImageAcquisitionError('The selected full-slide ImageGen route cannot fall back to API/background/template-shell generation')
    request = None
    api_returncode = None
    if resolution["path"] == PATH_API and execute_api:
        api_returncode = _run_api_generation(manifest_path, output_root)
        reconciliation = reconcile_manifest(manifest_path, output_dir=output_root, write=True)
    elif resolution["path"] == PATH_HOST_NATIVE:
        request = str(
            write_host_native_request(
                manifest_path,
                manifest,
                output_dir=output_root,
                request_path=request_path,
            )
        )
    elif resolution["path"] == PATH_MANUAL:
        changed = False
        for item in manifest["items"]:
            if item["status"] in RETRYABLE_STATUSES:
                item["status"] = STATUS_NEEDS_MANUAL
                item["last_error"] = "Manual image acquisition selected; place the file and run reconcile."
                changed = True
        if changed:
            save_manifest(str(manifest_path), manifest)
            reconciliation = reconcile_manifest(manifest_path, output_dir=output_root, write=True)
        request = str(
            render_manifest_md_to_file(str(manifest_path), load_image_resource_manifest(manifest_path))
        )
    sidecar = render_manifest_md_to_file(str(manifest_path), load_image_resource_manifest(manifest_path))
    return {
        "schema_version": SCHEMA,
        "status": "pass" if api_returncode in (None, 0) else "fail",
        "manifest": str(manifest_path),
        "output_dir": str(output_root),
        "resolution": resolution,
        "capability": resolution.get("capability", {}),
        "reconciliation": reconciliation,
        "request": request,
        "sidecar": sidecar,
        "api_returncode": api_returncode,
        "fallback": {
            "mode": "blocked_no_route_substitution" if manifest.get('purpose') == 'slide_reconstruction' else "template_shell",
            "pending_count": sum(
                1
                for item in load_image_resource_manifest(manifest_path).get("items", [])
                if isinstance(item, Mapping)
                and str(item.get("status") or "") in RETRYABLE_STATUSES | {STATUS_NEEDS_MANUAL}
            ),
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve PPT Master-style EasySlides image acquisition paths."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    capabilities = sub.add_parser("capabilities", help="Report configured API and host-native capabilities.")
    capabilities.add_argument("--host-native", action="store_true", help="Declare a host-native image tool for this run.")

    resolve = sub.add_parser("resolve", help="Resolve the deterministic acquisition path without changing files.")
    resolve.add_argument("manifest")
    resolve.add_argument("--path", choices=sorted(VALID_PATHS), default=None)
    resolve.add_argument("--host-native", action="store_true")

    reconcile = sub.add_parser("reconcile", help="Reconcile manifest statuses with files on disk.")
    reconcile.add_argument("manifest")
    reconcile.add_argument("--output-dir", default=None)

    scaffold = sub.add_parser("scaffold", help="Create cover/ending hero image resources for a deck topic.")
    scaffold.add_argument("manifest")
    scaffold.add_argument("--topic", required=True)
    scaffold.add_argument("--project", default=None)
    scaffold.add_argument("--rendering", default="vector-illustration")
    scaffold.add_argument("--palette", default="cool-corporate")
    scaffold.add_argument("--palette-id", default=None, help="Selected palette id from the template catalog.")
    scaffold.add_argument("--template-dir", default=None, help="Template directory used to resolve theme colors.")
    scaffold.add_argument("--primary", default="#1E3A5F")
    scaffold.add_argument("--secondary", default="#F8F9FA")
    scaffold.add_argument("--accent", default="#D4AF37")

    prepare = sub.add_parser("prepare", help="Prepare, execute, or hand off a manifest acquisition.")
    prepare.add_argument("manifest")
    prepare.add_argument("--path", choices=sorted(VALID_PATHS), default=None)
    prepare.add_argument("--host-native", action="store_true")
    prepare.add_argument("--output-dir", default=None)
    prepare.add_argument("--request-path", default=None)
    prepare.add_argument("--execute-api", action="store_true", help="Run existing image_gen.py when the selected path is api.")
    record = sub.add_parser('record-result', help='Record the actual full-slide ImageGen arguments and output.')
    record.add_argument('manifest')
    record.add_argument('--item', required=True)
    record.add_argument('--image', required=True)
    record.add_argument('--call', required=True, help='JSON with tool_name and actual tool_arguments.')
    record.add_argument('--output-dir')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        _load_image_env()
        if args.command == 'record-result':
            try:
                from scripts.image_generation_contract import record_result
            except ModuleNotFoundError:
                from image_generation_contract import record_result
            call = json.loads(Path(args.call).read_text(encoding='utf-8'))
            print(json.dumps(record_result(args.manifest, args.item, args.image, call, output_dir=args.output_dir), ensure_ascii=False, indent=2))
            return 0
        if args.command == "capabilities":
            print(
                json.dumps(
                    resolve_acquisition_path(
                        explicit_path=PATH_AUTO,
                        host_native_available=args.host_native or None,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "resolve":
            manifest = load_image_resource_manifest(args.manifest)
            print(
                json.dumps(
                    resolve_acquisition_path(
                        manifest,
                        explicit_path=args.path,
                        host_native_available=args.host_native or None,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "reconcile":
            print(json.dumps(reconcile_manifest(args.manifest, output_dir=args.output_dir), ensure_ascii=False, indent=2))
            return 0
        if args.command == "scaffold":
            target = scaffold_hero_manifest(
                args.manifest,
                topic=args.topic,
                project=args.project,
                rendering=args.rendering,
                palette=args.palette,
                palette_id=args.palette_id,
                template_dir=args.template_dir,
                primary=args.primary,
                secondary=args.secondary,
                accent=args.accent,
            )
            print(json.dumps({"schema_version": SCHEMA, "status": "pass", "manifest": str(target)}, ensure_ascii=False, indent=2))
            return 0
        report = prepare_acquisition(
            args.manifest,
            explicit_path=args.path,
            host_native_available=args.host_native or None,
            output_dir=args.output_dir,
            request_path=args.request_path,
            execute_api=args.execute_api,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1
    except (ImageAcquisitionError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
