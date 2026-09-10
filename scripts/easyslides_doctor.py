#!/usr/bin/env python3
"""Report local capabilities needed by the EasySlides product pipeline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.image_acquisition import detect_imagegen_capability, detect_imagegen_skill
    from scripts.theme_tokens import validate_tokens, resolve_template_tokens
    from scripts.template_capabilities import validate_capability_profile
except ModuleNotFoundError:  # pragma: no cover
    from image_acquisition import detect_imagegen_capability, detect_imagegen_skill
    from theme_tokens import validate_tokens, resolve_template_tokens
    from template_capabilities import validate_capability_profile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "easyslides.doctor_report.v1"


def _command_version(command: str, args: list[str] | None = None) -> dict[str, Any]:
    path = shutil.which(command)
    if not path:
        return {"available": False, "command": command}
    try:
        result = subprocess.run(
            [path, *(args or ["--version"])],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        text = (result.stdout or result.stderr).strip().splitlines()
        return {"available": result.returncode == 0, "command": command, "path": path, "version": text[0] if text else "", "exit_code": result.returncode}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "command": command, "path": path, "version_error": str(exc)}


def _module_check(name: str) -> dict[str, Any]:
    try:
        importlib.import_module(name)
        return {"available": True, "module": name}
    except (ImportError, OSError) as exc:
        return {"available": False, "module": name, "error": str(exc)}


def _powerpoint_check() -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "not_windows"}
    if not _module_check("win32com")["available"]:
        return {"available": False, "reason": "pywin32_missing"}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\CLSID") as key:
            winreg.QueryValue(key, None)
    except OSError:
        return {"available": False, "reason": "powerpoint_not_registered"}
    return {"available": None, "registered": True, "reason": "registered_but_render_not_verified"}


def _template_checks() -> list[dict[str, Any]]:
    policy_path = ROOT / "templates" / "template_policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"status": "fail", "error": f"cannot read template policy: {exc}"}]
    rows: list[dict[str, Any]] = []
    for template_id in policy.get("official_template_ids", []):
        template_dir = ROOT / "templates" / "layouts" / str(template_id)
        try:
            resolved = resolve_template_tokens(template_dir)
            validation = validate_tokens(resolved["tokens"])
            profile = validate_capability_profile(template_dir)
            rows.append({
                "template_id": template_id,
                "status": "pass" if validation["status"] == profile["status"] == "pass" else "fail",
                "palette_source": resolved["source"],
                "palette_id": resolved["palette_id"],
                "issues": validation["issues"] + profile["issues"],
            })
        except (OSError, ValueError) as exc:
            rows.append({"template_id": template_id, "status": "fail", "error": str(exc)})
    return rows


def build_report(*, host_native_imagegen: bool = False) -> dict[str, Any]:
    capability = detect_imagegen_capability(
        host_native_override=True if host_native_imagegen else None,
    )
    api_backend = str(os.environ.get("IMAGE_BACKEND") or "").strip()
    host_native = bool(capability["host_native_available"])
    skill_path = detect_imagegen_skill()
    checks: dict[str, Any] = {
        "python": {"available": True, "version": sys.version.split()[0], "path": sys.executable},
        "node": _command_version("node"),
        "npm": _command_version("npm"),
        "npx": _command_version("npx"),
        "powerpoint": _powerpoint_check(),
        "libreoffice": _command_version("soffice"),
        "pillow": _module_check("PIL"),
        "pptx": _module_check("pptx"),
        "lxml": _module_check("lxml"),
        "flask": _module_check("flask"),
        "image_generation": {
            **capability,
            "api_configured": bool(api_backend),
            "backend": api_backend or None,
            "host_native_available": bool(host_native),
            "imagegen_skill_available": skill_path is not None,
            "imagegen_skill": str(skill_path or ""),
            "available": bool(capability["available"]),
            "mode": capability["mode"],
        },
        "templates": _template_checks(),
    }
    template_failures = sum(row.get("status") != "pass" for row in checks["templates"])
    blockers = []
    warnings = []
    for module in ("pillow", "pptx", "lxml", "flask"):
        if not checks[module]["available"]:
            blockers.append(f"Required runtime dependency unavailable: {module}")
    if not checks["libreoffice"]["available"]:
        if checks["powerpoint"]["available"] is None:
            warnings.append("PowerPoint is registered; verify a real PPTX render before delivery")
        elif not checks["powerpoint"]["available"]:
            blockers.append("No verified PPTX renderer; install LibreOffice or configure PowerPoint")
    if not capability["available"]:
        warnings.append("Image generation is unverified; host must confirm callable tools or configure an API backend")
    if template_failures:
        blockers.append(f"{template_failures} official template(s) have invalid theme or capability contracts")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blockers else "needs_verification" if warnings else "pass",
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose EasySlides local runtime and image capabilities.")
    parser.add_argument("--host-native-imagegen", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(host_native_imagegen=args.host_native_imagegen)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"EasySlides doctor: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
