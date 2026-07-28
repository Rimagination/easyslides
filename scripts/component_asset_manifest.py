#!/usr/bin/env python3
"""Build deterministic media-asset manifests for component packs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import mimetypes
from typing import Any


SCHEMA_VERSION = "easyslides.asset_manifest.v1"
MANIFEST_NAME = "asset_manifest.json"
ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".woff", ".woff2"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path, *, exclude_names: set[str] | None = None) -> str:
    root = Path(root).resolve()
    excluded = exclude_names or set()
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name in excluded or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _asset_id(namespace: str, relative: Path) -> str:
    stem = relative.with_suffix("").as_posix()
    return f"media/{namespace}/{stem}" if namespace else f"media/{stem}"


def build_asset_manifest(assets_root: Path, *, namespace: str) -> dict[str, Any]:
    assets_root = Path(assets_root).resolve()
    rows: list[dict[str, Any]] = []
    if not assets_root.is_dir():
        return {
            "schema_version": SCHEMA_VERSION,
            "namespace": namespace,
            "asset_count": 0,
            "assets": [],
        }
    for path in sorted(assets_root.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_NAME or path.is_symlink():
            continue
        if path.suffix.lower() not in ASSET_SUFFIXES:
            continue
        relative = path.relative_to(assets_root)
        rows.append(
            {
                "asset_id": _asset_id(namespace, relative),
                "path": relative.as_posix(),
                "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": namespace,
        "asset_count": len(rows),
        "assets": rows,
    }


def materialize_asset_manifest(pack_root: Path, *, namespace: str) -> Path | None:
    assets_root = Path(pack_root) / "assets"
    manifest = build_asset_manifest(assets_root, namespace=namespace)
    if manifest["asset_count"] == 0:
        return None
    manifest_path = assets_root / MANIFEST_NAME
    assets_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def load_asset_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def validate_asset_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        manifest = load_asset_manifest(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "fail", "issue_count": 1, "issues": [{"code": "ASSET-MANIFEST-JSON", "message": str(exc)}]}
    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "ASSET-MANIFEST-SCHEMA", "message": f"schema_version must be {SCHEMA_VERSION}"})
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        issues.append({"code": "ASSET-MANIFEST-ASSETS", "message": "assets must be a list"})
        assets = []
    if manifest.get("asset_count") != len(assets):
        issues.append({"code": "ASSET-MANIFEST-COUNT", "message": "asset_count does not match assets"})
    seen: set[str] = set()
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            issues.append({"code": "ASSET-MANIFEST-ASSET", "message": f"assets[{index}] must be an object"})
            continue
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id or asset_id in seen:
            issues.append({"code": "ASSET-MANIFEST-ID", "message": f"invalid or duplicate asset_id at assets[{index}]"})
        seen.add(asset_id)
        for key in ("path", "mime_type", "sha256"):
            if not str(asset.get(key) or ""):
                issues.append({"code": "ASSET-MANIFEST-FIELD", "message": f"{key} is required at assets[{index}]"})
        raw_path = str(asset.get("path") or "").replace("\\", "/")
        relative_path = Path(raw_path)
        if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
            issues.append({"code": "ASSET-MANIFEST-PATH", "message": f"invalid asset path at assets[{index}]"})
            continue
        asset_path = path.parent / relative_path
        try:
            asset_path.resolve().relative_to(path.parent.resolve())
        except ValueError:
            issues.append({"code": "ASSET-MANIFEST-PATH", "message": f"asset path escapes manifest root at assets[{index}]"})
            continue
        if not asset_path.is_file():
            issues.append({"code": "ASSET-MANIFEST-MISSING", "message": f"asset file is missing at assets[{index}]"})
            continue
        if asset.get("bytes") is not None:
            try:
                expected_bytes = int(asset["bytes"])
            except (TypeError, ValueError):
                issues.append({"code": "ASSET-MANIFEST-SIZE", "message": f"asset byte count is invalid at assets[{index}]"})
            else:
                if expected_bytes != asset_path.stat().st_size:
                    issues.append({"code": "ASSET-MANIFEST-SIZE", "message": f"asset byte count is stale at assets[{index}]"})
        if asset.get("sha256") and str(asset["sha256"]) != _sha256(asset_path):
            issues.append({"code": "ASSET-MANIFEST-HASH", "message": f"asset sha256 is stale at assets[{index}]"})
    return {"status": "pass" if not issues else "fail", "issue_count": len(issues), "issues": issues, "asset_count": len(assets)}
