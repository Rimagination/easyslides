#!/usr/bin/env python3
"""Icon library inventory for EasySlides.

One command to answer "which icons does this deck need, and does the local
library actually have them?" — the question the executor currently answers
by importing a lucide catalog the repo doesn't ship.

Usage:
    python scripts/icon_inventory.py stats
        Per-library on-disk counts, plus lucide manifest-vs-disk gap.

    python scripts/icon_inventory.py missing <project_path>
        Scan <project>/svg_output/*.svg for <use data-icon="..."> refs and
        report refs whose icon file does not exist. Exit 1 when missing.

    python scripts/icon_inventory.py fetch --lib lucide --names rocket,terminal [--dry-run]
        Download missing icons from the lucide-static CDN into
        templates/icons/<lib>/. Explicit, opt-in, network-dependent.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = REPO_ROOT / 'templates' / 'icons'
MANIFEST_PATH = ICONS_DIR / 'icons_manifest.js'
LUCIDE_CDN = 'https://unpkg.com/lucide-static@latest/icons/{name}.svg'


def libraries_on_disk() -> dict[str, int]:
    """Library name -> number of .svg files on disk."""
    out: dict[str, int] = {}
    if not ICONS_DIR.is_dir():
        return out
    for child in sorted(ICONS_DIR.iterdir()):
        if child.is_dir():
            out[child.name] = len(list(child.glob('*.svg')))
    return out


def manifest_names() -> set[str]:
    """Best-effort extraction of the quoted name list in icons_manifest.js."""
    if not MANIFEST_PATH.exists():
        return set()
    text = MANIFEST_PATH.read_text(encoding='utf-8', errors='replace')
    return set(re.findall(r'"([a-z0-9][a-z0-9._-]*)"', text))


def project_icon_refs(project: Path) -> dict[str, set[str]]:
    """svg files -> set of data-icon refs used (across svg_output/)."""
    svg_dir = project / 'svg_output'
    if not svg_dir.is_dir():
        svg_dir = project
    refs: dict[str, set[str]] = {}
    for svg in sorted(svg_dir.glob('*.svg')):
        text = svg.read_text(encoding='utf-8', errors='replace')
        for name in re.findall(r'data-icon="([^"]+)"', text):
            refs.setdefault(name, set()).add(svg.name)
    return refs


def missing_on_disk(refs: set[str]) -> list[str]:
    """Refs whose icon file does not exist locally."""
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))
    from svg_finalize.embed_icons import resolve_icon_path
    missing = []
    for name in sorted(refs):
        path, _base = resolve_icon_path(name, ICONS_DIR)
        if not path.exists():
            missing.append(name)
    return missing


def cmd_stats(_args) -> int:
    disk = libraries_on_disk()
    print("Icon libraries on disk (templates/icons/):")
    for lib, count in disk.items():
        print(f"  {lib:<18} {count:>5} icons")
    disk_lucide = disk.get('lucide', 0)
    names = manifest_names()
    if names and 'lucide' in disk:
        available = {n for n in names if (ICONS_DIR / 'lucide' / f'{n}.svg').exists()}
        print(f"\nlucide manifest: {len(names)} names declared, "
              f"{len(available)} on disk, {len(names - available)} declared-but-missing")
        print("  -> the manifest promises more than the repo ships; either "
              "ship the assets, regenerate the manifest from disk, or use "
              "'fetch' to pull individual icons.")
        return 1 if len(names - available) > 0 else 0
    return 0


def cmd_missing(args) -> int:
    project = Path(args.project).resolve()
    if not project.exists():
        print(f"[ERROR] project not found: {project}")
        return 1
    refs = project_icon_refs(project)
    if not refs:
        print("No <use data-icon> references found in svg_output/.")
        return 0
    flat = set(refs.keys())
    missing = missing_on_disk(flat)
    file_count = len({f for files in refs.values() for f in files})
    print(f"{len(flat)} distinct icon refs across {file_count} file(s); "
          f"{len(missing)} missing:")
    for name in missing:
        users = sorted(refs.get(name, set()))
        print(f"  [MISSING] {name}  (used in: {', '.join(users[:3])}"
              f"{'…' if len(users) > 3 else ''})")
    if not missing:
        print("  all refs resolve — OK")
    return 1 if missing else 0


def cmd_fetch(args) -> int:
    names = [n.strip() for n in args.names.split(',') if n.strip()]
    target_lib = ICONS_DIR / args.lib
    if args.lib != 'lucide':
        print(f"[ERROR] fetch currently supports only --lib lucide "
              f"(CDN: {LUCIDE_CDN})")
        return 1
    target_lib.mkdir(parents=True, exist_ok=True)
    failures = []
    fetched = 0
    for name in names:
        dest = target_lib / f'{name}.svg'
        if dest.exists():
            print(f"  [skip] {name} (already on disk)")
            continue
        url = LUCIDE_CDN.format(name=name)
        if args.dry_run:
            print(f"  [dry-run] would fetch {url} -> {dest.relative_to(REPO_ROOT)}")
            continue
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                body = resp.read()
            if b'<svg' not in body:
                raise ValueError('response is not an SVG document')
            dest.write_bytes(body)
            fetched += 1
            print(f"  [ok] {name} -> {dest.relative_to(REPO_ROOT)}")
        except Exception as exc:
            failures.append(name)
            print(f"  [fail] {name}: {exc}")
    print(f"\nfetched {fetched}/{len(names)}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="EasySlides icon inventory.")
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('stats', help='Per-library counts + lucide manifest gap.')

    p_missing = sub.add_parser('missing', help='Project refs that lack files.')
    p_missing.add_argument('project', help='Project directory path.')
    p_missing.add_argument('--json', action='store_true', dest='as_json')

    p_fetch = sub.add_parser('fetch', help='Download missing lucide icons.')
    p_fetch.add_argument('--lib', default='lucide')
    p_fetch.add_argument('--names', required=True,
                         help='Comma-separated icon names.')
    p_fetch.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()
    if args.command == 'stats':
        sys.exit(cmd_stats(args))
    if args.command == 'missing':
        refs = project_icon_refs(Path(args.project).resolve())
        missing = missing_on_disk(set().union(*refs.values())) if refs else []
        if args.as_json:
            print(json.dumps({'missing': missing}, ensure_ascii=False))
        sys.exit(cmd_missing(args))
    if args.command == 'fetch':
        sys.exit(cmd_fetch(args))


if __name__ == '__main__':
    main()
