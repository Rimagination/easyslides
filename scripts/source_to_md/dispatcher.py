#!/usr/bin/env python3
"""Batch source-to-Markdown dispatcher.

This keeps EasySlides' per-format converters as the source of truth while
providing a single user-facing command for files, directories, and URLs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


TOOLS_DIR = Path(__file__).resolve().parents[1]
CONVERTER_DIR = Path(__file__).resolve().parent

PDF_SUFFIXES = {".pdf"}
PRESENTATION_SUFFIXES = {".pptx", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
LEGACY_EXCEL_SUFFIXES = {".xls"}
DOC_SUFFIXES = {
    ".docx", ".doc", ".odt", ".rtf",
    ".html", ".htm", ".epub", ".ipynb",
    ".tex", ".latex", ".rst", ".org", ".typ",
}
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
SUPPORTED_SUFFIXES = (
    PDF_SUFFIXES
    | PRESENTATION_SUFFIXES
    | EXCEL_SUFFIXES
    | LEGACY_EXCEL_SUFFIXES
    | DOC_SUFFIXES
    | TEXT_SUFFIXES
)


@dataclass
class ConversionRoute:
    source: str
    output: str | None
    kind: str
    command: list[str] | None
    status: str = "pending"
    error: str | None = None


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_name(value: str) -> str:
    safe = re.sub(r"[^\w.\-]+", "_", value, flags=re.UNICODE).strip("._")
    return safe[:100] or "source"


def derive_url_basename(url: str) -> str:
    parsed = urlparse(url)
    parts = [sanitize_name(parsed.netloc)]
    if parsed.path and parsed.path != "/":
        parts.append(sanitize_name(parsed.path.strip("/").replace("/", "_")))
    return "_".join(part for part in parts if part) or "web_source"


def output_path_for(source: str, output: str | None, multiple: bool) -> Path | None:
    if is_url(source):
        stem = derive_url_basename(source)
    else:
        stem = Path(source).stem

    if output:
        out = Path(output)
        if multiple or out.suffix.lower() != ".md":
            return out / f"{stem}.md"
        return out

    if is_url(source):
        return Path.cwd() / "projects" / f"{stem}.md"

    return Path(source).with_suffix(".md")


def detect_kind(source: str) -> str:
    if is_url(source):
        return "web"
    suffix = Path(source).suffix.lower()
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix in PRESENTATION_SUFFIXES:
        return "pptx"
    if suffix in EXCEL_SUFFIXES:
        return "excel"
    if suffix in LEGACY_EXCEL_SUFFIXES:
        return "legacy_excel"
    if suffix in DOC_SUFFIXES:
        return "doc"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".txt":
        return "text"
    return "unsupported"


def build_command(route: ConversionRoute, *, images: str, max_rows: int, max_cols: int) -> list[str] | None:
    if route.output is None:
        return None
    output = route.output
    if route.kind == "pdf":
        return [
            sys.executable,
            str(CONVERTER_DIR / "pdf_to_md.py"),
            route.source,
            "-o",
            output,
            "--images",
            images,
        ]
    if route.kind == "pptx":
        return [
            sys.executable,
            str(CONVERTER_DIR / "ppt_to_md.py"),
            route.source,
            "-o",
            output,
        ]
    if route.kind == "excel":
        return [
            sys.executable,
            str(CONVERTER_DIR / "excel_to_md.py"),
            route.source,
            "-o",
            output,
            "--max-rows",
            str(max_rows),
            "--max-cols",
            str(max_cols),
        ]
    if route.kind == "doc":
        return [
            sys.executable,
            str(CONVERTER_DIR / "doc_to_md.py"),
            route.source,
            "-o",
            output,
        ]
    if route.kind == "web":
        return [
            sys.executable,
            str(CONVERTER_DIR / "web_to_md.py"),
            route.source,
            "-o",
            output,
        ]
    return None


def expand_inputs(inputs: list[str], *, recursive: bool) -> list[str]:
    expanded: list[str] = []
    for item in inputs:
        if is_url(item):
            expanded.append(item)
            continue
        path = Path(item)
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            files = sorted(
                child for child in iterator
                if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES
            )
            expanded.extend(str(child) for child in files)
            continue
        expanded.append(item)
    return expanded


def write_profile(route: ConversionRoute) -> None:
    if not route.output:
        return
    profile_path = Path(route.output).with_suffix(".conversion_profile.json")
    profile_path.write_text(
        json.dumps(
            {
                **asdict(route),
                "converted_at": datetime.now().isoformat(timespec="seconds"),
                "dispatcher": "scripts/source_to_md.py",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def copy_text_source(route: ConversionRoute) -> None:
    if route.output is None:
        raise ValueError("Missing output path")
    source = Path(route.source)
    output = Path(route.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if route.kind == "markdown":
        shutil.copy2(source, output)
        return
    content = source.read_text(encoding="utf-8", errors="replace")
    output.write_text(content, encoding="utf-8")


def run_route(route: ConversionRoute, *, dry_run: bool) -> ConversionRoute:
    if route.kind in {"unsupported", "legacy_excel"}:
        route.status = "failed"
        route.error = (
            "Legacy .xls is not converted automatically; resave as .xlsx"
            if route.kind == "legacy_excel"
            else "Unsupported input type"
        )
        return route

    if route.command is None and route.kind not in {"markdown", "text"}:
        route.status = "failed"
        route.error = "No conversion command for route"
        return route

    if dry_run:
        route.status = "dry-run"
        return route

    try:
        if route.kind in {"markdown", "text"}:
            copy_text_source(route)
        else:
            assert route.command is not None
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8:replace"
            subprocess.run(
                route.command,
                check=True,
                cwd=TOOLS_DIR.parent,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        route.status = "converted"
    except Exception as exc:
        route.status = "failed"
        route.error = str(exc)

    write_profile(route)
    return route


def build_routes(args: argparse.Namespace) -> list[ConversionRoute]:
    sources = expand_inputs(args.inputs, recursive=args.recursive)
    multiple = len(sources) > 1
    routes: list[ConversionRoute] = []
    for source in sources:
        kind = detect_kind(source)
        output = output_path_for(source, args.output, multiple)
        route = ConversionRoute(
            source=source,
            output=str(output) if output is not None else None,
            kind=kind,
            command=None,
        )
        route.command = build_command(
            route,
            images=args.images,
            max_rows=args.max_rows,
            max_cols=args.max_cols,
        )
        routes.append(route)
    return routes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert files, directories, or URLs to Markdown through one dispatcher",
    )
    parser.add_argument("inputs", nargs="+", help="Files, directories, or URLs to convert")
    parser.add_argument(
        "-o",
        "--output",
        help="Output .md for a single input, or output directory for multiple inputs",
    )
    parser.add_argument("--recursive", action="store_true", help="Recursively expand directories")
    parser.add_argument("--dry-run", action="store_true", help="Print planned routes without converting")
    parser.add_argument("--json", action="store_true", help="Print route summary as JSON")
    parser.add_argument(
        "--images",
        choices=["all", "filtered", "none"],
        default="filtered",
        help="PDF image extraction mode",
    )
    parser.add_argument("--max-rows", type=int, default=0, help="Excel row cap per sheet, 0 = no limit")
    parser.add_argument("--max-cols", type=int, default=0, help="Excel column cap per sheet, 0 = no limit")
    return parser


def print_summary(routes: list[ConversionRoute], *, as_json: bool) -> None:
    data = [asdict(route) for route in routes]
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    for route in routes:
        target = route.output or "(none)"
        command = " ".join(route.command or [])
        print(f"[{route.status}] {route.kind}: {route.source} -> {target}")
        if command:
            print(f"  command: {command}")
        if route.error:
            print(f"  error: {route.error}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_rows < 0 or args.max_cols < 0:
        parser.error("--max-rows and --max-cols must be zero or positive integers")

    routes = build_routes(args)
    if not routes:
        print("[ERROR] No supported inputs found", file=sys.stderr)
        return 1

    results = [run_route(route, dry_run=args.dry_run) for route in routes]
    print_summary(results, as_json=args.json)
    return 0 if all(route.status in {"converted", "dry-run"} for route in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
