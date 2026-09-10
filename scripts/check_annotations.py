#!/usr/bin/env python3
"""
PPT Master - SVG Annotation Checker

Scans SVG files for edit annotations (data-edit-target / data-edit-annotation attributes)
and prints a human-readable summary. Used by AI agents to discover pending annotations.

Usage:
    python3 scripts/check_annotations.py <project_dir>
    python3 scripts/check_annotations.py <svg_file>

Examples:
    python3 scripts/check_annotations.py projects/my-project
    python3 scripts/check_annotations.py projects/my-project/svg_output/slide_01.svg

Dependencies:
    None (only uses standard library)
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def scan_svg_file(svg_path: Path) -> list[dict]:
    """Scan a single SVG file for edit annotations."""
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return []

    root = tree.getroot()
    annotations = []

    for elem in root.iter():
        if elem.get('data-edit-target') == 'true':
            tag = elem.tag
            if '}' in tag:
                tag = tag.split('}', 1)[1]

            content_preview = ''
            if tag == 'text' and elem.text:
                content_preview = elem.text.strip()[:50]

            annotations.append({
                'element_id': elem.get('id', '(no id)'),
                'tag': tag,
                'annotation': elem.get('data-edit-annotation', ''),
                'content_preview': content_preview,
            })

    return annotations


def scan_directory(dir_path: Path) -> dict[str, list[dict]]:
    """Read source-image regions and existing SVG element annotations."""
    results = {}
    review_path = dir_path / 'source_image_review.json'
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding='utf-8'))
        if review.get('schema_version') != 'easyslides.source_image_review.v1':
            raise ValueError('Unsupported source-image review schema')
        for item in review.get('annotations', []):
            if item.get('status') != 'pending':
                continue
            key = f"imagegen original: {item['slide']}"
            results.setdefault(key, []).append({
                'element_id': item['id'], 'tag': 'source-region',
                'annotation': item['annotation'],
                'content_preview': f"pixels {item['box']}",
                'source_image': item['source_image'],
                'preserve_unselected': True,
            })
    svg_dir = dir_path / 'svg_output'
    if not svg_dir.exists():
        return results

    for svg_file in sorted(svg_dir.glob('*.svg')):
        annotations = scan_svg_file(svg_file)
        if annotations:
            results[svg_file.name] = annotations

    return results


def print_results(results: dict[str, list[dict]]) -> None:
    """Print annotation results in human-readable format."""
    if not results:
        print("[OK] No annotations found.")
        return

    total = sum(len(anns) for anns in results.values())
    file_count = len(results)
    ann_word = "annotation" if total == 1 else "annotations"
    file_word = "file" if file_count == 1 else "files"
    print(f"Found {total} {ann_word} in {file_count} {file_word}:\n")

    for filename, annotations in results.items():
        print(f"{filename}")
        for i, ann in enumerate(annotations, 1):
            content = f' "{ann["content_preview"]}"' if ann['content_preview'] else ''
            print(f"  [{i}] <{ann['tag']} id=\"{ann['element_id']}\">{content}")
            print(f"      → {ann['annotation']}")
            if ann.get('source_image'):
                print(f"      Source: {ann['source_image']}")
                print('      Reconstruct from the original image. Preserve unselected content; do not use editable PPTX as reference.')
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Check SVG files for edit annotations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('path', help='Project directory or single SVG file path')
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    if target.is_file() and target.suffix == '.svg':
        annotations = scan_svg_file(target)
        results = {target.name: annotations} if annotations else {}
    elif target.is_dir():
        results = scan_directory(target)
    else:
        print(f"Error: Expected a project directory or .svg file, got: {target}", file=sys.stderr)
        return 1

    print_results(results)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
