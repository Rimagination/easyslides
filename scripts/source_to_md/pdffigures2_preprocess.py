"""PDFFigures2 fallback for scholarly figure/table extraction.

This wrapper intentionally keeps the contract small for EasySlides:
configured PDFFigures2 output -> Markdown + normalized figures directory.

Configuration:
- `PDFFIGURES2_CMD`: command template, for example
  `java -jar C:\\tools\\pdffigures2.jar {pdf} -d {out}`
- `PDFFIGURES2_JAR`: jar path fallback. Uses
  `java -jar <jar> <pdf> -d <out>`.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
REPO_ROOT = Path(__file__).resolve().parents[2]


class PDFFigures2Error(RuntimeError):
    """PDFFigures2 extraction error."""


def _format_command(template: str, *, pdf_path: Path, raw_dir: Path) -> list[str]:
    command = template.format(pdf=str(pdf_path), out=str(raw_dir))
    return shlex.split(command, posix=os.name != "nt")


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key.strip(), value


def _read_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            values[parsed[0]] = parsed[1]
    return values


def _env_candidates() -> list[Path]:
    candidates = [Path.cwd() / ".env", REPO_ROOT / ".env"]
    try:
        candidates.append(Path.home() / ".ppt-master" / ".env")
    except RuntimeError:
        pass
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def _env_value(key: str, env_paths: Iterable[Path] = ()) -> str | None:
    if os.environ.get(key):
        return os.environ[key].strip()
    for env_path in [*env_paths, *_env_candidates()]:
        value = _read_env_file(env_path).get(key)
        if value:
            return value
    return None


def _pdffigures2_command(
    pdf_path: Path,
    raw_dir: Path,
    env_paths: Iterable[Path] = (),
) -> list[str]:
    template = _env_value("PDFFIGURES2_CMD", env_paths)
    if template:
        return _format_command(template, pdf_path=pdf_path, raw_dir=raw_dir)

    jar = _env_value("PDFFIGURES2_JAR", env_paths)
    if jar:
        return ["java", "-jar", jar, str(pdf_path), "-d", str(raw_dir)]

    raise PDFFigures2Error(
        "PDFFigures2 is not configured. Set PDFFIGURES2_CMD or PDFFIGURES2_JAR."
    )


def _run_pdffigures2(pdf_path: Path, raw_dir: Path) -> None:
    command = _pdffigures2_command(pdf_path, raw_dir)
    result = subprocess.run(
        command,
        cwd=raw_dir.parent,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise PDFFigures2Error(details or f"PDFFigures2 failed with exit code {result.returncode}")


def _caption_lookup(raw_dir: Path) -> dict[str, str]:
    captions: dict[str, str] = {}
    for json_path in raw_dir.rglob("*.json"):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items: list[Any]
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("figures") or payload.get("items") or [payload]
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            caption = str(item.get("caption") or item.get("captionText") or "").strip()
            for key in ("renderURL", "imagePath", "filename", "name"):
                value = item.get(key)
                if value and caption:
                    captions[Path(str(value)).name] = caption
    return captions


def _normalize_figures(raw_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    figures_dir = raw_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    captions = _caption_lookup(raw_dir)
    source_images = [
        path
        for path in sorted(raw_dir.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in IMAGE_SUFFIXES
        and figures_dir not in path.parents
    ]
    if not source_images:
        source_images = [
            path
            for path in sorted(figures_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]

    assets: list[dict[str, Any]] = []
    for index, source in enumerate(source_images, start=1):
        if figures_dir in source.parents:
            dest = source
        else:
            dest = figures_dir / f"fig-{index:03d}{source.suffix.lower()}"
            shutil.copy2(source, dest)
        assets.append(
            {
                "id": f"fig-{index:03d}",
                "filename": dest.name,
                "path": str(dest),
                "caption": captions.get(source.name, ""),
                "source_path": str(source),
            }
        )
    if not assets:
        raise PDFFigures2Error("PDFFigures2 produced no figure/table images.")
    return figures_dir, assets


def _write_outputs(output_dir: Path, file_stem: str, raw_dir: Path, figures_dir: Path, assets: list[dict[str, Any]]) -> Path:
    markdown_path = output_dir / f"{file_stem}_pdffigures2.md"
    lines = [f"# {file_stem} - PDFFigures2 assets", ""]
    for asset in assets:
        caption = asset["caption"] or asset["id"]
        rel = Path(raw_dir.name) / "figures" / asset["filename"]
        lines.extend([f"## {asset['id']}", "", f"![{caption}]({rel.as_posix()})", ""])
        if asset["caption"]:
            lines.extend([asset["caption"], ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")

    index = {
        "schema": "easyslides.pdffigures2.asset-index.v1",
        "asset_count": len(assets),
        "assets": assets,
    }
    (raw_dir / "pdffigures2_manifest.json").write_text(
        json.dumps(
            {
                "method": "pdffigures2",
                "markdown_path": str(markdown_path),
                "figures_dir": str(figures_dir),
                "asset_count": len(assets),
                "asset_index_json": str(raw_dir / "assets_index.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "assets_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return markdown_path


def extract_pdf(pdf_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Extract scholarly figures/tables via PDFFigures2 and normalize outputs."""
    pdf = Path(pdf_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / f"{pdf.stem}_pdffigures2"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True)

    _run_pdffigures2(pdf, raw_dir)
    figures_dir, assets = _normalize_figures(raw_dir)
    markdown_path = _write_outputs(output, pdf.stem, raw_dir, figures_dir, assets)
    return {
        "method": "pdffigures2",
        "markdown_path": str(markdown_path),
        "figures_dir": str(figures_dir),
        "asset_index_json": str(raw_dir / "assets_index.json"),
        "manifest_path": str(raw_dir / "pdffigures2_manifest.json"),
    }
