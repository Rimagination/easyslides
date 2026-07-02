#!/usr/bin/env python3
"""Render a PPTX deck to per-slide PNG files for visual QA."""

from __future__ import annotations

import argparse
import json
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
Runner = Callable[..., subprocess.CompletedProcess]


def _slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def _clear_prior_slide_pngs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("slide*.png"):
        if path.is_file():
            path.unlink()


def _normalize_slide_pngs(output_dir: Path) -> list[Path]:
    files = sorted(output_dir.glob("slide*.png"), key=_slide_number)
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
    executable = soffice_executable or shutil.which("soffice") or shutil.which("libreoffice")
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
) -> dict[str, Any]:
    pptx = Path(pptx_path).resolve()
    output = Path(output_dir).resolve()
    if not pptx.exists():
        raise FileNotFoundError(f"PPTX not found: {pptx}")
    _clear_prior_slide_pngs(output)

    with tempfile.TemporaryDirectory() as temp_dir_raw:
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

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if files else "fail",
        "pptx_path": str(pptx),
        "output_dir": str(output),
        "renderer": renderer,
        "dpi": dpi,
        "slide_count": len(files),
        "files": [path.name for path in files],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", help="PPTX file to render.")
    parser.add_argument("--out", required=True, help="Output directory for slide_###.png files.")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--report", help="Optional render report JSON path.")
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
