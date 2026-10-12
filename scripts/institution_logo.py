#!/usr/bin/env python3
"""Fetch a ScanSci logo for an explicitly identified user institution."""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from PIL import Image


ORIGIN = "https://www.scansci.com"
PROVIDER = ORIGIN + "/logos/"
API = ORIGIN + "/api/logos"
VARIANTS = ("emblem", "brand", "lockup_horizontal", "lockup_vertical", "wordmark")
MAX_BYTES = 8 * 1024 * 1024


def _read(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "EasySlides/ScanSci-Logos"})
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("logo response exceeds 8 MiB")
    return data


def _write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def fetch_logo(
    project: str | Path,
    institution: str = "",
    *,
    variant: str | None = None,
    timeout: float = 20,
) -> dict:
    """Resolve an exact name/domain; unsuccessful lookups retain the placeholder.

    The caller identifies the user's affiliation before calling. Do not pass a
    template name, a cited author's affiliation, or an inferred topic here.
    """
    if variant is not None and variant not in VARIANTS:
        raise ValueError(f"unsupported logo variant: {variant}")
    query = institution.strip()
    project = Path(project).resolve()
    assets = project / "assets" / "logos"
    assets.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "easyslides.institution_logo.v1",
        "provider": PROVIDER,
        "query": query,
        "requested_variant": variant,
        "status": "fallback",
        "reason": "institution_not_identified",
        "fallback": "keep_template_placeholder",
        "asset_path": None,
        "metadata": None,
    }
    if query:
        image_request = False
        try:
            params = {"q": query}
            if variant:
                params["variant"] = variant
            metadata = json.loads(_read(API + "/resolve?" + urlencode(params), timeout))
            if not isinstance(metadata, dict):
                raise ValueError("institution metadata must be an object")
            report["metadata"] = metadata
            asset = metadata.get("asset") or {}
            if not isinstance(asset, dict):
                raise ValueError("institution asset metadata must be an object")
            chosen_variant = asset.get("variant")
            if variant and chosen_variant != variant:
                report["reason"] = "variant_unavailable"
            elif not metadata.get("image_url") or asset.get("review_status") != "reviewed":
                report["reason"] = "image_unavailable"
            else:
                identifier = str(metadata.get("id") or "")
                revision = str(asset.get("revision") or "")
                if (chosen_variant not in VARIANTS or
                        not all(re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in (identifier, revision))):
                    raise ValueError("invalid institution asset identifier")
                image_url = urljoin(ORIGIN + "/", metadata["image_url"])
                parsed = urlsplit(image_url)
                if (parsed.scheme != "https" or parsed.netloc not in {"www.scansci.com", "scansci.com"}
                        or not parsed.path.startswith("/logo-assets/")):
                    raise ValueError("logo URL must be a published ScanSci static asset")
                suffix = Path(parsed.path).suffix.lower()
                expected_format = {".png": "PNG", ".webp": "WEBP"}.get(suffix)
                if not expected_format:
                    raise ValueError("logo image_url must provide PNG or WebP")
                path = assets / f"{identifier}_{chosen_variant}_{revision}{suffix}"
                image_request = True
                data = path.read_bytes() if path.is_file() else _read(image_url, timeout)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != expected_format:
                        raise ValueError("downloaded logo does not match its image format")
                    dimensions = image.size
                    image.verify()
                if not path.is_file():
                    _write_atomic(path, data)
                report.update(
                    status="resolved", reason="exact_institution_match", fallback=None,
                    asset_path=path.relative_to(project).as_posix(),
                    image_url=image_url, width_px=dimensions[0], height_px=dimensions[1],
                )
        except HTTPError as exc:
            report["reason"] = ("image_unavailable" if image_request else
                                {404: "institution_not_found", 409: "institution_ambiguous"}.get(exc.code, "http_error"))
            report["http_status"] = exc.code
            if exc.code == 409:
                try:
                    error = json.loads(exc.read(MAX_BYTES))
                    if isinstance(error, dict):
                        report["candidates"] = error.get("candidates", [])
                except (OSError, ValueError):
                    pass
        except (OSError, ValueError, TypeError, TimeoutError, SyntaxError, Image.DecompressionBombError) as exc:
            report.update(reason="resource_unavailable", error=str(exc))
    _write_atomic(assets / "institution_logo.json", (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a ScanSci logo for an explicitly identified user institution.")
    parser.add_argument("project", type=Path, help="Deck project receiving assets/logos/ and provenance JSON.")
    parser.add_argument("--institution", default="", help="Identified user institution name or official domain.")
    parser.add_argument("--variant", choices=VARIANTS, help="Default: the provider's emblem/brand choice; never substitute a missing variant.")
    args = parser.parse_args(argv)
    try:
        report = fetch_logo(args.project, args.institution, variant=args.variant)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
