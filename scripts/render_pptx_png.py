#!/usr/bin/env python3
"""Render a PPTX deck to per-slide PNG files for visual QA."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.office.soffice import get_soffice_env
except ImportError:  # pragma: no cover - direct script execution
    from office.soffice import get_soffice_env


SCHEMA_VERSION = "easyslides.pptx_render_png_report.v1"
POWERPOINT_RENDER_SCRIPT = Path(__file__).resolve().parent / "office" / "render_powerpoint.ps1"
Runner = Callable[..., subprocess.CompletedProcess]


def _existing_executable(value: str | Path | None) -> str | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate)
    return shutil.which(str(value))


def _registry_powerpoint_paths() -> list[str]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    locations = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\POWERPNT.EXE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\POWERPNT.EXE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\POWERPNT.EXE"),
    )
    paths: list[str] = []
    for hive, key_path in locations:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, None)
        except OSError:
            continue
        if value:
            paths.append(str(value))
    return paths


def _find_powerpoint_executable(explicit: str | Path | None = None) -> str | None:
    """Find PowerPoint used by the native COM renderer."""
    candidates: list[str | Path] = []
    if explicit:
        candidates.append(explicit)
    for command in ("POWERPNT.EXE", "powerpnt.exe", "powerpnt"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)
    candidates.extend(_registry_powerpoint_paths())

    program_roots = {
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    }
    for root in program_roots:
        for office_dir in ("Office16", "Office15", "Office14"):
            candidates.extend(
                (
                    root / "Microsoft Office" / "root" / office_dir / "POWERPNT.EXE",
                    root / "Microsoft Office" / office_dir / "POWERPNT.EXE",
                )
            )

    for candidate in candidates:
        path = _existing_executable(candidate)
        if path:
            return path
    return None


def _find_powershell_executable(explicit: str | Path | None = None) -> str | None:
    candidates: list[str | Path] = []
    if explicit:
        candidates.append(explicit)
    for command in ("powershell.exe", "pwsh.exe", "powershell", "pwsh"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)
    candidates.append(
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    for candidate in candidates:
        path = _existing_executable(candidate)
        if path:
            return path
    return None


def _find_soffice_executable(explicit: str | Path | None = None) -> str | None:
    if explicit:
        # Keep explicit paths injectable for tests and remote runners.
        return str(explicit)
    return shutil.which("soffice") or shutil.which("libreoffice")


def _slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def _slide_pngs(output_dir: Path) -> list[Path]:
    return [
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".png"
    ]


def _clear_prior_slide_pngs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in _slide_pngs(output_dir):
        path.unlink()


def _normalize_slide_pngs(output_dir: Path) -> list[Path]:
    files = sorted(_slide_pngs(output_dir), key=_slide_number)
    normalized: list[Path] = []
    for index, path in enumerate(files, start=1):
        target = output_dir / f"slide_{index:03d}.png"
        if path.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            path.rename(target)
        normalized.append(target)
    return normalized


def _convert_pptx_to_pdf(
    pptx_path: Path,
    temp_dir: Path,
    *,
    runner: Runner,
    soffice_executable: str | None,
) -> Path:
    executable = _find_soffice_executable(soffice_executable)
    if executable is None:
        raise FileNotFoundError("LibreOffice executable not found: install soffice/libreoffice or add it to PATH.")
    command = [
        executable,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(temp_dir),
        str(pptx_path),
    ]
    result = runner(command, capture_output=True, text=True, env=get_soffice_env())
    pdf_path = temp_dir / f"{pptx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError("LibreOffice PDF conversion failed.")
    return pdf_path


def _render_with_powerpoint(
    pptx_path: Path,
    output_dir: Path,
    *,
    dpi: int,
    runner: Runner,
    powershell_executable: str | None = None,
) -> list[Path]:
    powershell = _find_powershell_executable(powershell_executable)
    if not powershell:
        raise FileNotFoundError("PowerShell executable not found: required for Microsoft PowerPoint COM rendering.")
    if not POWERPOINT_RENDER_SCRIPT.is_file():
        raise FileNotFoundError(f"PowerPoint render helper not found: {POWERPOINT_RENDER_SCRIPT}")

    command = [
        powershell,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(POWERPOINT_RENDER_SCRIPT),
        "-PptxPath",
        str(pptx_path),
        "-OutputDir",
        str(output_dir),
        "-Dpi",
        str(dpi),
    ]
    completed = runner(command, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown PowerPoint error").strip()
        raise RuntimeError(f"Microsoft PowerPoint PNG export failed: {detail}")

    files = _normalize_slide_pngs(output_dir)
    if not files:
        raise RuntimeError("Microsoft PowerPoint PNG export completed without producing slide images.")
    return files


def _select_renderer_backend(
    renderer_backend: str,
    powerpoint_executable: str | None,
    soffice_executable: str | None,
) -> str:
    if renderer_backend not in {"auto", "powerpoint", "soffice"}:
        raise ValueError(f"Unsupported renderer backend: {renderer_backend}")
    if renderer_backend == "powerpoint":
        if not _find_powerpoint_executable(powerpoint_executable):
            raise FileNotFoundError("Microsoft PowerPoint executable not found.")
        return "powerpoint"
    if renderer_backend == "soffice":
        if not _find_soffice_executable(soffice_executable):
            raise FileNotFoundError("LibreOffice executable not found: install soffice/libreoffice or add it to PATH.")
        return "soffice"

    # An explicit --soffice path keeps the legacy command deterministic.
    if soffice_executable:
        return "soffice"
    if _find_powerpoint_executable(powerpoint_executable):
        return "powerpoint"
    if _find_soffice_executable():
        return "soffice"
    raise FileNotFoundError(
        "No PPTX renderer found: install Microsoft PowerPoint or LibreOffice, or pass an explicit renderer path."
    )


def _render_pdf_with_pdftoppm(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int,
    runner: Runner,
    pdftoppm_executable: str,
) -> list[Path]:
    command = [
        pdftoppm_executable,
        "-png",
        "-r",
        str(dpi),
        str(pdf_path),
        str(output_dir / "slide"),
    ]
    result = runner(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("pdftoppm PNG rendering failed.")
    return _normalize_slide_pngs(output_dir)


def _render_pdf_with_pymupdf(pdf_path: Path, output_dir: Path, *, dpi: int) -> list[Path]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise FileNotFoundError("pdftoppm is unavailable and PyMuPDF is not installed.") from exc

    doc = fitz.open(pdf_path)
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)
    files: list[Path] = []
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        path = output_dir / f"slide_{index:03d}.png"
        pix.save(path)
        files.append(path)
    doc.close()
    return files


def render_pptx_to_png(
    pptx_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 144,
    runner: Runner = subprocess.run,
    soffice_executable: str | None = None,
    pdftoppm_executable: str | None = None,
    renderer_backend: str = "auto",
    powerpoint_executable: str | None = None,
    powershell_executable: str | None = None,
) -> dict[str, Any]:
    pptx = Path(pptx_path).resolve()
    output = Path(output_dir).resolve()
    if not pptx.exists():
        raise FileNotFoundError(f"PPTX not found: {pptx}")
    _clear_prior_slide_pngs(output)

    backend = _select_renderer_backend(renderer_backend, powerpoint_executable, soffice_executable)
    fallback_reason: str | None = None
    files: list[Path]
    if backend == "powerpoint":
        try:
            files = _render_with_powerpoint(
                pptx,
                output,
                dpi=dpi,
                runner=runner,
                powershell_executable=powershell_executable,
            )
            renderer = "powerpoint"
        except Exception as exc:
            if renderer_backend != "auto":
                raise
            fallback_soffice = _find_soffice_executable()
            if not fallback_soffice:
                raise
            fallback_reason = str(exc)
            _clear_prior_slide_pngs(output)
            backend = "soffice"

    if backend == "soffice":
        with tempfile.TemporaryDirectory(prefix="easyslides-render-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            pdf_path = _convert_pptx_to_pdf(
                pptx,
                temp_dir,
                runner=runner,
                soffice_executable=soffice_executable,
            )
            pdftoppm = pdftoppm_executable or shutil.which("pdftoppm")
            if pdftoppm:
                files = _render_pdf_with_pdftoppm(
                    pdf_path,
                    output,
                    dpi=dpi,
                    runner=runner,
                    pdftoppm_executable=pdftoppm,
                )
                renderer = "pdftoppm"
            else:
                files = _render_pdf_with_pymupdf(pdf_path, output, dpi=dpi)
                renderer = "pymupdf"

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if files else "fail",
        "pptx_path": str(pptx),
        "output_dir": str(output),
        "backend": backend,
        "renderer": renderer,
        "dpi": dpi,
        "slide_count": len(files),
        "files": [path.name for path in files],
    }
    if fallback_reason:
        report["fallback_reason"] = fallback_reason
    return report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", help="PPTX file to render.")
    parser.add_argument("--out", required=True, help="Output directory for slide_###.png files.")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--report", help="Optional render report JSON path.")
    parser.add_argument(
        "--renderer",
        choices=("auto", "powerpoint", "soffice"),
        default="auto",
        help="Rendering backend; auto prefers native PowerPoint on Windows and falls back to LibreOffice.",
    )
    parser.add_argument("--powerpoint", help="Optional POWERPNT.EXE path.")
    parser.add_argument("--powershell", help="Optional PowerShell executable path.")
    parser.add_argument("--soffice", help="Explicit soffice/libreoffice executable path.")
    parser.add_argument("--pdftoppm", help="Explicit pdftoppm executable path.")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = render_pptx_to_png(
            args.pptx,
            args.out,
            dpi=args.dpi,
            renderer_backend=args.renderer,
            powerpoint_executable=args.powerpoint,
            powershell_executable=args.powershell,
            soffice_executable=args.soffice,
            pdftoppm_executable=args.pdftoppm,
        )
    except Exception as exc:
        report = {"schema_version": SCHEMA_VERSION, "status": "fail", "error": str(exc)}
        if args.report:
            _write_json(Path(args.report), report)
        if not args.quiet:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if args.report:
        _write_json(Path(args.report), report)
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
