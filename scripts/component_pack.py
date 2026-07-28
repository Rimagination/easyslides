#!/usr/bin/env python3
"""Validate and install declarative EasySlides component packs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKAGES_ROOT = ROOT / "templates" / "components" / "packages"
INSTALLED_PACKS_ROOT = ROOT / "templates" / "components" / "installed"
DEFAULT_INSTALL_ROOT = INSTALLED_PACKS_ROOT
DEFAULT_REGISTRY = ROOT / "templates" / "components" / "component_registry.json"
PACK_SCHEMA_VERSION = "easyslides.component_pack.v1"
PACK_REPORT_SCHEMA_VERSION = "easyslides.component_pack_report.v1"
LOCK_SCHEMA_VERSION = "easyslides.component_pack_lock.v1"
ARCHIVE_DIR = ".archive"
PACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
COMPONENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SUPPORTED_RENDER_BACKENDS = {"component_package"}
SUPPORTED_TRUST_MODE = "declarative_only"
SUPPORTED_TOKEN_MODES = {"self_contained", "template_inherit"}
ALLOWED_ASSET_SUFFIXES = {
    ".json",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".md",
    ".txt",
    ".woff",
    ".woff2",
}
ALLOWED_ROOT_FILES = {
    "pack.json",
    "pack.lock.json",
    "readme.md",
    "license",
    "license.md",
    "license.txt",
    "changelog.md",
    ".gitignore",
}

try:
    from scripts.component_package import validate_component_package
    from scripts.component_registry import build_component_registry, validate_component_registry
    from scripts.component_asset_manifest import build_asset_manifest, materialize_asset_manifest, tree_sha256, validate_asset_manifest
    from scripts.component_renderer_registry import resolve_renderer_id, validate_renderer_id
except ModuleNotFoundError:  # pragma: no cover
    from component_package import validate_component_package
    from component_registry import build_component_registry, validate_component_registry
    from component_asset_manifest import build_asset_manifest, materialize_asset_manifest, tree_sha256, validate_asset_manifest
    from component_renderer_registry import resolve_renderer_id, validate_renderer_id


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _issue(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_relative_path(root: Path, value: Any) -> Path | None:
    if not _nonempty(value):
        return None
    raw = str(value).replace("\\", "/")
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _validate_file_policy(pack_root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in pack_root.rglob("*"):
        relative = path.relative_to(pack_root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            issues.append(_issue("COMPONENT-PACK-SYMLINK", "symlinks are not allowed in a component pack", relative.as_posix()))
            continue
        if not path.is_file():
            continue
        if len(relative.parts) == 1:
            if path.name.lower() not in ALLOWED_ROOT_FILES:
                issues.append(_issue("COMPONENT-PACK-FILE", "unexpected root file; packs are declarative assets only", relative.as_posix()))
            continue
        if relative.parts[0] not in {"components", "assets"}:
            issues.append(_issue("COMPONENT-PACK-FILE", "files must live under components/ or assets/", relative.as_posix()))
            continue
        if path.suffix.lower() not in ALLOWED_ASSET_SUFFIXES:
            issues.append(_issue("COMPONENT-PACK-FILE", "file type is not allowed in a declarative component pack", relative.as_posix()))
    return issues


def _token_value(tokens: dict[str, Any], dotted_path: str) -> Any:
    value: Any = tokens
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _validate_pack_dependencies(manifest: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    issues: list[dict[str, str]] = []
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict):
        return ([_issue("COMPONENT-PACK-DEPENDENCIES", "dependencies must be an object", "dependencies")], [])
    packs = dependencies.get("component_packs")
    if not isinstance(packs, list):
        return ([_issue("COMPONENT-PACK-DEPENDENCIES", "dependencies.component_packs must be a list", "dependencies.component_packs")], [])
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, dependency in enumerate(packs):
        path = f"dependencies.component_packs[{index}]"
        if not isinstance(dependency, dict):
            issues.append(_issue("COMPONENT-PACK-DEPENDENCIES", "component-pack dependency must be an object", path))
            continue
        pack_id = str(dependency.get("pack_id") or "")
        version_range = str(dependency.get("version_range") or "")
        if not PACK_ID_RE.fullmatch(pack_id):
            issues.append(_issue("COMPONENT-PACK-DEPENDENCIES", "dependency pack_id must be a lowercase slug", f"{path}.pack_id"))
            continue
        if not _nonempty(version_range):
            issues.append(_issue("COMPONENT-PACK-DEPENDENCIES", "dependency version_range is required", f"{path}.version_range"))
        if pack_id in seen:
            issues.append(_issue("COMPONENT-PACK-DEPENDENCIES", f"duplicate dependency {pack_id!r}", f"{path}.pack_id"))
        seen.add(pack_id)
        if "optional" in dependency and not isinstance(dependency.get("optional"), bool):
            issues.append(_issue("COMPONENT-PACK-DEPENDENCIES", "dependency optional must be boolean", f"{path}.optional"))
        normalized.append(
            {
                "pack_id": pack_id,
                "version_range": version_range,
                "optional": bool(dependency.get("optional", False)),
            }
        )
    return issues, normalized


def _validate_design_tokens(pack_root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    declaration = manifest.get("design_tokens")
    if not isinstance(declaration, dict):
        return ([_issue("COMPONENT-PACK-TOKENS", "design_tokens must be an object", "design_tokens")], {})
    mode = str(declaration.get("mode") or "")
    if mode not in SUPPORTED_TOKEN_MODES:
        issues.append(_issue("COMPONENT-PACK-TOKENS", f"design_tokens.mode must be one of {', '.join(sorted(SUPPORTED_TOKEN_MODES))}", "design_tokens.mode"))
    required = declaration.get("required")
    if not isinstance(required, list) or not required or not all(_nonempty(token) for token in required):
        issues.append(_issue("COMPONENT-PACK-TOKENS", "design_tokens.required must be a non-empty list of token paths", "design_tokens.required"))
        required = []
    source_text = str(declaration.get("source") or "")
    source = _safe_relative_path(pack_root, source_text) if source_text else None
    tokens: dict[str, Any] = {}
    if mode == "self_contained":
        if source is None or not source.is_file():
            issues.append(_issue("COMPONENT-PACK-TOKENS", "self-contained design tokens require a local JSON source", "design_tokens.source"))
        else:
            try:
                tokens = _read_json(source)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                issues.append(_issue("COMPONENT-PACK-TOKENS", f"invalid design token file: {exc}", "design_tokens.source"))
            for token_path in required:
                if _token_value(tokens, str(token_path)) is None:
                    issues.append(_issue("COMPONENT-PACK-TOKENS", f"required token {token_path!r} is missing", "design_tokens.required"))
    elif source_text and source is None:
        issues.append(_issue("COMPONENT-PACK-TOKENS", "design_tokens.source must stay inside the pack", "design_tokens.source"))
    return issues, {
        "mode": mode,
        "source": source_text,
        "required": list(required),
    }


def _semver_parts(version: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _version_satisfies(version: str, version_range: str) -> bool:
    current = _semver_parts(version)
    requirement = version_range.strip()
    if current is None or not requirement:
        return False
    if requirement in {"*", "latest"}:
        return True
    if requirement.startswith("^"):
        minimum = _semver_parts(requirement[1:])
        return minimum is not None and current >= minimum and current[0] == minimum[0]
    if requirement.startswith("~"):
        minimum = _semver_parts(requirement[1:])
        return minimum is not None and current >= minimum and current[:2] == minimum[:2]
    for term in requirement.split():
        operator = "="
        candidate = term
        for prefix in (">=", "<=", ">", "<", "="):
            if term.startswith(prefix):
                operator = prefix
                candidate = term[len(prefix):]
                break
        expected = _semver_parts(candidate)
        if expected is None:
            return False
        if operator == ">=" and not current >= expected:
            return False
        if operator == "<=" and not current <= expected:
            return False
        if operator == ">" and not current > expected:
            return False
        if operator == "<" and not current < expected:
            return False
        if operator == "=" and not current == expected:
            return False
    return True


def _available_pack_versions(roots: list[Path]) -> dict[str, list[str]]:
    versions: dict[str, list[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        for manifest_path in root.rglob("pack.json"):
            if any(part in {".git", ".archive", ".staging"} for part in manifest_path.relative_to(root).parts):
                continue
            try:
                manifest = _read_json(manifest_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            pack_id = str(manifest.get("pack_id") or "")
            version = str(manifest.get("version") or "")
            if PACK_ID_RE.fullmatch(pack_id) and _semver_parts(version):
                versions.setdefault(pack_id, []).append(version)
    return versions


def resolve_component_pack_dependencies(
    manifest: dict[str, Any],
    *,
    roots: list[Path],
) -> dict[str, Any]:
    """Resolve declarative dependencies without running pack-supplied code."""
    dependencies = manifest.get("dependencies") if isinstance(manifest.get("dependencies"), dict) else {}
    rows = dependencies.get("component_packs") if isinstance(dependencies.get("component_packs"), list) else []
    available = _available_pack_versions(roots)
    issues: list[dict[str, str]] = []
    resolved: list[dict[str, Any]] = []
    current_pack_id = str(manifest.get("pack_id") or "")
    for index, dependency in enumerate(rows):
        if not isinstance(dependency, dict):
            continue
        pack_id = str(dependency.get("pack_id") or "")
        version_range = str(dependency.get("version_range") or "")
        optional = bool(dependency.get("optional", False))
        path = f"dependencies.component_packs[{index}]"
        if pack_id == current_pack_id:
            issues.append(_issue("COMPONENT-PACK-DEPENDENCY-SELF", "a component pack cannot depend on itself", f"{path}.pack_id"))
            continue
        matches = [version for version in available.get(pack_id, []) if _version_satisfies(version, version_range)]
        if not matches and not optional:
            issues.append(
                _issue(
                    "COMPONENT-PACK-DEPENDENCY-MISSING",
                    f"required dependency {pack_id!r} does not satisfy {version_range!r}",
                    path,
                )
            )
        resolved.append(
            {
                "pack_id": pack_id,
                "version_range": version_range,
                "optional": optional,
                "resolved_versions": sorted(matches),
                "status": "resolved" if matches else ("optional_missing" if optional else "missing"),
            }
        )
    return {"status": "pass" if not issues else "fail", "issues": issues, "dependencies": resolved}


def validate_component_pack(pack_root: Path) -> dict[str, Any]:
    pack_root = Path(pack_root).resolve()
    issues: list[dict[str, str]] = []
    manifest_path = pack_root / "pack.json"
    manifest: dict[str, Any] = {}
    if not pack_root.is_dir():
        issues.append(_issue("COMPONENT-PACK-ROOT", "pack root must be a directory", str(pack_root)))
    elif not manifest_path.is_file():
        issues.append(_issue("COMPONENT-PACK-MANIFEST", "pack.json is required", "pack.json"))
    else:
        try:
            manifest = _read_json(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            issues.append(_issue("COMPONENT-PACK-MANIFEST", f"invalid pack.json: {exc}", "pack.json"))

    if manifest:
        if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
            issues.append(_issue("COMPONENT-PACK-SCHEMA", f"schema_version must be {PACK_SCHEMA_VERSION}", "schema_version"))
        pack_id = str(manifest.get("pack_id") or "")
        if not PACK_ID_RE.fullmatch(pack_id):
            issues.append(_issue("COMPONENT-PACK-ID", "pack_id must be a lowercase slug of 2-64 characters", "pack_id"))
        version = str(manifest.get("version") or "")
        if not SEMVER_RE.fullmatch(version):
            issues.append(_issue("COMPONENT-PACK-VERSION", "version must use semantic versioning", "version"))
        for key in ("display_name", "description", "license"):
            if not _nonempty(manifest.get(key)):
                issues.append(_issue("COMPONENT-PACK-FIELD", f"{key} is required", key))

        trust = manifest.get("trust")
        if not isinstance(trust, dict):
            issues.append(_issue("COMPONENT-PACK-TRUST", "trust must be an object", "trust"))
        else:
            if trust.get("mode") != SUPPORTED_TRUST_MODE:
                issues.append(_issue("COMPONENT-PACK-TRUST", f"trust.mode must be {SUPPORTED_TRUST_MODE}", "trust.mode"))
            permissions = trust.get("permissions", [])
            if permissions not in ([], None):
                issues.append(_issue("COMPONENT-PACK-PERMISSIONS", "component packs cannot request runtime permissions", "trust.permissions"))
            if trust.get("code_execution") is True:
                issues.append(_issue("COMPONENT-PACK-CODE", "executable pack code is not supported", "trust.code_execution"))
        dependency_issues, dependencies = _validate_pack_dependencies(manifest)
        token_issues, token_contract = _validate_design_tokens(pack_root, manifest)
        issues.extend(dependency_issues)
        issues.extend(token_issues)
    else:
        dependencies = []
        token_contract = {}

    declared_components = manifest.get("components") if isinstance(manifest, dict) else None
    if not isinstance(declared_components, list) or not declared_components:
        issues.append(_issue("COMPONENT-PACK-COMPONENTS", "components must be a non-empty list", "components"))
        declared_components = []

    component_ids: set[str] = set()
    component_paths: set[str] = set()
    component_rows: list[dict[str, Any]] = []
    for index, entry in enumerate(declared_components):
        entry_path = f"components[{index}]"
        if not isinstance(entry, dict):
            issues.append(_issue("COMPONENT-PACK-COMPONENT", "component entry must be an object", entry_path))
            continue
        component_id = str(entry.get("component_id") or "")
        relative_value = entry.get("path")
        component_dir = _safe_relative_path(pack_root, relative_value)
        relative_text = str(relative_value or "")
        if not COMPONENT_ID_RE.fullmatch(component_id):
            issues.append(_issue("COMPONENT-PACK-COMPONENT-ID", "component_id must be a lowercase slug", f"{entry_path}.component_id"))
        if component_id in component_ids:
            issues.append(_issue("COMPONENT-PACK-COMPONENT-ID", f"duplicate component_id {component_id!r}", f"{entry_path}.component_id"))
        component_ids.add(component_id)
        if component_dir is None or component_dir == pack_root:
            issues.append(_issue("COMPONENT-PACK-COMPONENT-PATH", "component path must stay inside the pack", f"{entry_path}.path"))
            continue
        normalized_path = component_dir.relative_to(pack_root).as_posix()
        if normalized_path in component_paths:
            issues.append(_issue("COMPONENT-PACK-COMPONENT-PATH", f"duplicate component path {normalized_path!r}", f"{entry_path}.path"))
        component_paths.add(normalized_path)
        package_path = component_dir / "component.json"
        if not package_path.is_file():
            issues.append(_issue("COMPONENT-PACK-COMPONENT-PATH", "component path must contain component.json", f"{entry_path}.path"))
            continue
        try:
            package = _read_json(package_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            issues.append(_issue("COMPONENT-PACK-COMPONENT", f"invalid component.json: {exc}", f"{normalized_path}/component.json"))
            continue
        if package.get("component_id") != component_id:
            issues.append(_issue("COMPONENT-PACK-COMPONENT-ID", "manifest component_id must match component.json", f"{normalized_path}/component.json"))
        if package.get("asset_id") != f"component_package/{component_id}":
            issues.append(_issue("COMPONENT-PACK-ASSET-ID", "component asset_id must be component_package/<component_id>", f"{normalized_path}/component.json"))
        if package.get("render_backend") not in SUPPORTED_RENDER_BACKENDS:
            issues.append(_issue("COMPONENT-PACK-RENDERER", "pack component uses an unsupported render_backend", f"{normalized_path}/component.json"))
        renderer_id = resolve_renderer_id(package)
        renderer_report = validate_renderer_id(renderer_id)
        if renderer_report["status"] != "pass":
            issues.append(_issue("COMPONENT-PACK-RENDERER", renderer_report["issues"][0], f"{normalized_path}/component.json"))
        package_report = validate_component_package(component_dir, package)
        for item in package_report.get("issues", []):
            issues.append(_issue(item["code"], item["message"], f"{normalized_path}/{item['path']}"))
        component_rows.append(
            {
                "component_id": component_id,
                "path": normalized_path or relative_text,
                "status": package_report.get("status", "fail"),
                "story_count": package_report.get("story_count", 0),
            }
        )

    issues.extend(_validate_file_policy(pack_root))
    asset_manifest_path = pack_root / "assets" / "asset_manifest.json"
    if asset_manifest_path.is_file():
        asset_report = validate_asset_manifest(asset_manifest_path)
        for item in asset_report.get("issues", []):
            issues.append(_issue(item["code"], item["message"], "assets/asset_manifest.json"))
    asset_count = 0
    if manifest:
        asset_count = int(build_asset_manifest(pack_root / "assets", namespace=str(manifest.get("pack_id") or ""))["asset_count"])
    return {
        "schema_version": PACK_REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "pack_id": str(manifest.get("pack_id") or ""),
        "version": str(manifest.get("version") or ""),
        "display_name": str(manifest.get("display_name") or ""),
        "component_count": len(component_rows),
        "asset_count": asset_count,
        "dependencies": dependencies,
        "design_tokens": token_contract,
        "components": component_rows,
        "manifest": manifest,
    }


def _github_source(source: str) -> tuple[str, str | None] | None:
    if not source.startswith("github:"):
        return None
    body = source.removeprefix("github:").strip().strip("/")
    if not body:
        return None
    ref = None
    if "@" in body:
        body, ref = body.rsplit("@", 1)
    if body.count("/") != 1:
        return None
    return f"https://github.com/{body}.git", ref or None


def _is_git_source(source: str) -> bool:
    return bool(_github_source(source)) or source.startswith(("https://", "http://", "git@"))


def _generic_git_source(source: str) -> tuple[str, str | None] | None:
    if not _is_git_source(source) or _github_source(source):
        return None
    url, separator, ref = source.partition("#")
    if not url:
        return None
    return url, ref if separator and ref else None


@contextmanager
def _materialize_source(source: str | Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    source_text = str(source)
    github = _github_source(source_text)
    generic_git = _generic_git_source(source_text)
    if not github and not generic_git:
        source_path = Path(source_text).resolve()
        yield source_path, {"type": "local", "path": str(source_path)}
        return

    with tempfile.TemporaryDirectory(prefix="easyslides-component-pack-") as temporary:
        clone_dir = Path(temporary) / "repo"
        url, ref = github or generic_git or (source_text, None)
        command = ["git", "clone", "--depth", "1"]
        if ref:
            command.extend(["--branch", ref])
        command.extend([url, str(clone_dir)])
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "git clone failed").strip()
            raise RuntimeError(detail)
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone_dir,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else ""
        yield clone_dir, {
            "type": "git",
            "requested": source_text,
            "url": url,
            "ref": ref or "HEAD",
            "commit": commit,
        }


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _pack_version(pack_path: Path) -> str:
    try:
        return str(_read_json(pack_path / "pack.json").get("version") or "unknown")
    except (OSError, json.JSONDecodeError, ValueError):
        return "unknown"


def _archive_existing_pack(install_path: Path, target_root: Path) -> Path:
    archive_path = target_root / ARCHIVE_DIR / install_path.name / f"{_pack_version(install_path)}-{_timestamp_slug()}"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(install_path), str(archive_path))
    return archive_path


def _write_install_lock(
    install_path: Path,
    *,
    source_metadata: dict[str, Any],
    content_sha256: str,
) -> Path:
    manifest = _read_json(install_path / "pack.json")
    lock = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "pack_id": manifest.get("pack_id", ""),
        "version": manifest.get("version", ""),
        "source": source_metadata,
        "content_sha256": content_sha256,
        "locked_at": datetime.now(timezone.utc).isoformat(),
    }
    lock_path = install_path / "pack.lock.json"
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lock_path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with open(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _restore_installation(install_path: Path, archive_path: Path | None) -> None:
    if install_path.exists():
        shutil.rmtree(install_path)
    if archive_path and archive_path.exists():
        install_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archive_path), str(install_path))


def _build_installed_registry(
    installed_root: Path,
    *,
    include_installed: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = build_component_registry(
        packages_root=PACKAGES_ROOT,
        additional_packages_roots=[installed_root] if include_installed else [],
    )
    return registry, validate_component_registry(registry)


def install_component_pack(
    source: str | Path,
    *,
    target: str | Path = DEFAULT_INSTALL_ROOT,
    force: bool = False,
    rebuild_registry: bool | None = None,
    registry_output: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    target_root = Path(target).resolve()
    archive_path: Path | None = None
    install_path: Path | None = None
    activated = False
    try:
        with _materialize_source(source) as (pack_root, source_metadata):
            validation = validate_component_pack(pack_root)
            if validation["status"] != "pass":
                return {**validation, "operation": "install", "status": "fail"}
            pack_id = validation["pack_id"]
            target_root.mkdir(parents=True, exist_ok=True)
            dependency_report = resolve_component_pack_dependencies(
                validation["manifest"],
                roots=[PACKAGES_ROOT, target_root],
            )
            if dependency_report["status"] != "pass":
                return {
                    **validation,
                    "operation": "install",
                    "status": "fail",
                    "issue_count": len(dependency_report["issues"]),
                    "issues": dependency_report["issues"],
                    "dependency_report": dependency_report,
                }
            install_path = (target_root / pack_id).resolve()
            if install_path.parent != target_root or install_path.name != pack_id:
                return {
                    "schema_version": PACK_REPORT_SCHEMA_VERSION,
                    "operation": "install",
                    "status": "fail",
                    "issue_count": 1,
                    "issues": [_issue("COMPONENT-PACK-TARGET", "install target escaped the selected directory", "target")],
                }
            if install_path.exists() and not force:
                return {
                    **validation,
                    "operation": "install",
                    "status": "fail",
                    "issue_count": 1,
                    "issues": [_issue("COMPONENT-PACK-EXISTS", "pack is already installed; pass --force to replace it", str(install_path))],
                }

            staging_root = Path(tempfile.mkdtemp(prefix=".staging-", dir=target_root))
            staged_pack = staging_root / pack_id
            try:
                shutil.copytree(pack_root, staged_pack, ignore=shutil.ignore_patterns(".git"))
                if install_path.exists():
                    archive_path = _archive_existing_pack(install_path, target_root)
                materialize_asset_manifest(staged_pack, namespace=pack_id)
                content_sha256 = tree_sha256(staged_pack, exclude_names={"pack.lock.json", "asset_manifest.json"})
                shutil.move(str(staged_pack), str(install_path))
                activated = True
                _write_install_lock(
                    install_path,
                    source_metadata=source_metadata,
                    content_sha256=content_sha256,
                )
            finally:
                shutil.rmtree(staging_root, ignore_errors=True)

            registry_report: dict[str, Any] = {"status": "skipped"}
            should_rebuild = rebuild_registry if rebuild_registry is not None else target_root == DEFAULT_INSTALL_ROOT.resolve()
            if should_rebuild:
                registry, registry_report = _build_installed_registry(target_root)
                if registry_report["status"] != "pass":
                    _restore_installation(install_path, archive_path)
                    return {
                        **validation,
                        "operation": "install",
                        "status": "fail",
                        "issue_count": registry_report["issue_count"],
                        "issues": registry_report["issues"],
                        "registry": registry_report,
                    }
                registry_path = Path(registry_output).resolve()
                _atomic_write_text(registry_path, json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
            return {
                **validation,
                "operation": "install",
                "status": "pass",
                "installed_path": str(install_path),
                "registry": registry_report,
                "dependency_report": dependency_report,
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "archive_path": str(archive_path) if archive_path else None,
            }
    except (OSError, RuntimeError, ValueError) as exc:
        if activated and install_path is not None:
            try:
                if archive_path is not None:
                    _restore_installation(install_path, archive_path)
                elif install_path.exists():
                    shutil.rmtree(install_path)
            except OSError:
                pass
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "install",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-INSTALL", str(exc), "source")],
        }


def _write_current_registry(target_root: Path, registry_output: str | Path) -> dict[str, Any]:
    registry, report = _build_installed_registry(target_root)
    if report["status"] != "pass":
        return {"status": "fail", "report": report}
    output_path = Path(registry_output).resolve()
    _atomic_write_text(output_path, json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    return {"status": "pass", "report": report, "path": str(output_path)}


def remove_component_pack(
    pack_id: str,
    *,
    target: str | Path = DEFAULT_INSTALL_ROOT,
    registry_output: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    target_root = Path(target).resolve()
    if not PACK_ID_RE.fullmatch(pack_id):
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "remove",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-ID", "pack_id must be a lowercase slug", "pack_id")],
        }
    install_path = target_root / pack_id
    if not install_path.is_dir():
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "remove",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-NOT-INSTALLED", f"pack {pack_id!r} is not installed", str(install_path))],
        }
    archive_path = _archive_existing_pack(install_path, target_root)
    try:
        registry_result = _write_current_registry(target_root, registry_output)
        if registry_result["status"] != "pass":
            _restore_installation(install_path, archive_path)
            return {
                "schema_version": PACK_REPORT_SCHEMA_VERSION,
                "operation": "remove",
                "status": "fail",
                "issue_count": registry_result["report"]["issue_count"],
                "issues": registry_result["report"]["issues"],
            }
    except OSError as exc:
        _restore_installation(install_path, archive_path)
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "remove",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-REMOVE", str(exc), str(archive_path))],
        }
    return {
        "schema_version": PACK_REPORT_SCHEMA_VERSION,
        "operation": "remove",
        "status": "pass",
        "issue_count": 0,
        "issues": [],
        "pack_id": pack_id,
        "archive_path": str(archive_path),
    }


def rollback_component_pack(
    pack_id: str,
    *,
    version: str | None = None,
    target: str | Path = DEFAULT_INSTALL_ROOT,
    registry_output: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    target_root = Path(target).resolve()
    if not PACK_ID_RE.fullmatch(pack_id):
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "rollback",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-ID", "pack_id must be a lowercase slug", "pack_id")],
        }
    archive_root = target_root / ARCHIVE_DIR / pack_id
    candidates = [path for path in sorted(archive_root.iterdir()) if path.is_dir()] if archive_root.is_dir() else []
    if version:
        candidates = [path for path in candidates if _pack_version(path) == version]
    if not candidates:
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "rollback",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-NO-ROLLBACK", f"no archived version found for {pack_id!r}", str(archive_root))],
        }
    selected = candidates[-1]
    install_path = target_root / pack_id
    current_archive: Path | None = None
    activated = False
    if install_path.exists():
        current_archive = _archive_existing_pack(install_path, target_root)
    try:
        shutil.move(str(selected), str(install_path))
        activated = True
        registry_result = _write_current_registry(target_root, registry_output)
        if registry_result["status"] != "pass":
            if install_path.exists():
                selected.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(install_path), str(selected))
            if current_archive and current_archive.exists():
                shutil.move(str(current_archive), str(install_path))
            return {
                "schema_version": PACK_REPORT_SCHEMA_VERSION,
                "operation": "rollback",
                "status": "fail",
                "issue_count": registry_result["report"]["issue_count"],
                "issues": registry_result["report"]["issues"],
            }
    except OSError as exc:
        if activated and install_path.exists():
            selected.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(install_path), str(selected))
        if current_archive and current_archive.exists():
            shutil.move(str(current_archive), str(install_path))
        return {
            "schema_version": PACK_REPORT_SCHEMA_VERSION,
            "operation": "rollback",
            "status": "fail",
            "issue_count": 1,
            "issues": [_issue("COMPONENT-PACK-ROLLBACK", str(exc), str(selected))],
        }
    return {
        "schema_version": PACK_REPORT_SCHEMA_VERSION,
        "operation": "rollback",
        "status": "pass",
        "issue_count": 0,
        "issues": [],
        "pack_id": pack_id,
        "version": _pack_version(install_path),
    }


def list_component_packs(root: str | Path = DEFAULT_INSTALL_ROOT) -> dict[str, Any]:
    root_path = Path(root).resolve()
    packs: list[dict[str, Any]] = []
    if root_path.exists():
        for manifest_path in sorted(root_path.rglob("pack.json")):
            if any(part in {".git", ARCHIVE_DIR, ".staging"} for part in manifest_path.relative_to(root_path).parts):
                continue
            try:
                manifest = _read_json(manifest_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
                continue
            packs.append(
                {
                    "pack_id": manifest.get("pack_id", ""),
                    "version": manifest.get("version", ""),
                    "display_name": manifest.get("display_name", ""),
                    "path": str(manifest_path.parent),
                    "component_count": len(manifest.get("components", [])) if isinstance(manifest.get("components"), list) else 0,
                }
            )
    return {
        "schema_version": PACK_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "root": str(root_path),
        "pack_count": len(packs),
        "packs": packs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and install declarative EasySlides component packs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a component pack directory.")
    validate.add_argument("pack", type=Path)
    validate.add_argument("--json", action="store_true")

    install = subparsers.add_parser("install", help="Install a local path, Git URL, or github:owner/repo pack.")
    install.add_argument("source")
    install.add_argument("--target", type=Path, default=DEFAULT_INSTALL_ROOT)
    install.add_argument("--registry-output", type=Path, default=DEFAULT_REGISTRY)
    install.add_argument("--force", action="store_true")
    install.add_argument("--no-registry", action="store_true", help="Skip rebuilding the component registry.")
    install.add_argument("--json", action="store_true")

    update = subparsers.add_parser("update", help="Replace an installed pack and archive its previous version.")
    update.add_argument("source")
    update.add_argument("--target", type=Path, default=DEFAULT_INSTALL_ROOT)
    update.add_argument("--registry-output", type=Path, default=DEFAULT_REGISTRY)
    update.add_argument("--json", action="store_true")

    remove = subparsers.add_parser("remove", help="Archive the active version of an installed pack.")
    remove.add_argument("pack_id")
    remove.add_argument("--target", type=Path, default=DEFAULT_INSTALL_ROOT)
    remove.add_argument("--registry-output", type=Path, default=DEFAULT_REGISTRY)
    remove.add_argument("--json", action="store_true")

    rollback = subparsers.add_parser("rollback", help="Restore an archived version of an installed pack.")
    rollback.add_argument("pack_id")
    rollback.add_argument("--version")
    rollback.add_argument("--target", type=Path, default=DEFAULT_INSTALL_ROOT)
    rollback.add_argument("--registry-output", type=Path, default=DEFAULT_REGISTRY)
    rollback.add_argument("--json", action="store_true")

    listing = subparsers.add_parser("list", help="List installed component packs.")
    listing.add_argument("--root", type=Path, default=DEFAULT_INSTALL_ROOT)
    listing.add_argument("--json", action="store_true")
    return parser


def _print_report(report: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    operation = report.get("operation", "list")
    print(f"Component pack {operation}: {report.get('status', 'unknown')}")
    if report.get("pack_id"):
        print(f"- {report['pack_id']} {report.get('version', '')}".rstrip())
    if report.get("installed_path"):
        print(f"- installed: {report['installed_path']}")
    for item in report.get("issues", []):
        print(f"- {item['code']}: {item['message']} [{item['path']}]")
    if operation == "list":
        for pack in report.get("packs", []):
            print(f"- {pack['pack_id']} {pack['version']} ({pack['component_count']} component(s))")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        report = validate_component_pack(args.pack)
        _print_report(report, args.json)
        return 0 if report["status"] == "pass" else 1
    if args.command == "install":
        report = install_component_pack(
            args.source,
            target=args.target,
            force=args.force,
            rebuild_registry=False if args.no_registry else None,
            registry_output=args.registry_output,
        )
        _print_report(report, args.json)
        return 0 if report["status"] == "pass" else 1
    if args.command == "update":
        report = install_component_pack(
            args.source,
            target=args.target,
            force=True,
            registry_output=args.registry_output,
        )
        _print_report(report, args.json)
        return 0 if report["status"] == "pass" else 1
    if args.command == "remove":
        report = remove_component_pack(args.pack_id, target=args.target, registry_output=args.registry_output)
        _print_report(report, args.json)
        return 0 if report["status"] == "pass" else 1
    if args.command == "rollback":
        report = rollback_component_pack(
            args.pack_id,
            version=args.version,
            target=args.target,
            registry_output=args.registry_output,
        )
        _print_report(report, args.json)
        return 0 if report["status"] == "pass" else 1
    report = list_component_packs(args.root)
    _print_report(report, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
