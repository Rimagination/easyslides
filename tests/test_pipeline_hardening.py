# -*- coding: utf-8 -*-
"""Tests for the pipeline hardening changes (branch fix/pipeline-hardening).

Covers:
- icon preflight: find_missing_icon_refs + checker integration
- font entity normalization in spec_lock drift comparison
- CJK-aware text overflow estimation
- slide filter parsing in visual_review
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from svg_quality_checker import (  # noqa: E402
    SVGQualityChecker,
    _decode_svg_entities,
    _estimate_text_width_px,
)
from svg_finalize.embed_icons import find_missing_icon_refs  # noqa: E402


# ---------------------------------------------------------------- helpers

def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


SVG_TMPL = (
    '<svg width="1280" height="720" viewBox="0 0 1280 720" '
    'xmlns="http://www.w3.org/2000/svg">{body}</svg>'
)

LOCK_OK = (
    '# Execution Lock\n'
    '\n'
    '## canvas\n'
    '- viewBox: 0 0 1280 720\n'
    '\n'
    '## colors\n'
    '- primary: #E8590C\n'
    '\n'
    '## typography\n'
    '- font_family: "Microsoft YaHei", Arial, sans-serif\n'
    '- body: 19\n'
)


# ---------------------------------------------------------------- entities

def test_decode_svg_entities():
    assert _decode_svg_entities('&quot;Microsoft YaHei&quot;, Arial') == \
        '"Microsoft YaHei", Arial'
    assert _decode_svg_entities('R&amp;D') == 'R&D'
    assert _decode_svg_entities('plain') == 'plain'


def test_font_drift_not_flagged_for_quoted_stack(tmp_path):
    """The regression from the codex_orange_book_pitch run: quoted font
    stacks written as &quot;…&quot; in SVG attributes must not drift against
    a lock that holds the decoded characters."""
    svg = _write(tmp_path / 'svg_output' / 'a.svg', SVG_TMPL.format(
        body='<text x="10" y="20" font-size="19" '
             'font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" '
             'fill="#E8590C">你好</text>'))
    _write(tmp_path / 'spec_lock.md', LOCK_OK)
    checker = SVGQualityChecker()
    result = checker.check_file(str(svg))
    assert result['passed']
    drift = [w for w in result['warnings'] if 'font' in w.lower()
             and 'drift' in w.lower()]
    assert not drift, drift


# ---------------------------------------------------------------- icons

def test_find_missing_icon_refs(tmp_path):
    lib = tmp_path / 'icons' / 'tabler-outline'
    lib.mkdir(parents=True)
    (lib / 'rocket.svg').write_text('<svg></svg>', encoding='utf-8')
    svg = (
        '<svg><use data-icon="tabler-outline/rocket"/>'
        '<use data-icon="tabler-outline/nope"/></svg>'
    )
    missing = find_missing_icon_refs(svg, tmp_path / 'icons')
    assert missing == ['tabler-outline/nope']


def test_checker_errors_on_missing_icon(tmp_path):
    svg = _write(tmp_path / 'svg_output' / 'a.svg', SVG_TMPL.format(
        body='<use data-icon="tabler-outline/definitely-not-here"/>'))
    _write(tmp_path / 'spec_lock.md', LOCK_OK)
    checker = SVGQualityChecker()
    result = checker.check_file(str(svg))
    assert not result['passed']
    assert any('Icon not found in library' in e for e in result['errors'])


# ---------------------------------------------------------------- overflow

def test_width_estimator_cjk_vs_latin():
    cjk = _estimate_text_width_px('你好世界', 20)
    latin = _estimate_text_width_px('HELLO', 20)
    assert cjk == 4 * 20          # full-width glyphs
    assert latin == 5 * 20 * 0.62  # uppercase latin


def test_checker_warns_on_overflowing_line(tmp_path):
    long_line = '这是一段非常长的中文文本' * 20  # ~840px at 21px
    svg = _write(tmp_path / 'svg_output' / 'a.svg', SVG_TMPL.format(
        body=f'<text x="1200" y="20" font-size="21" '
             f'font-family="Arial, sans-serif" fill="#000000">'
             f'{long_line}</text>'))
    _write(tmp_path / 'spec_lock.md', LOCK_OK)
    checker = SVGQualityChecker()
    result = checker.check_file(str(svg))
    assert any('Possible text overflow' in w for w in result['warnings'])
    # warning must not fail the file
    assert result['passed']


def test_checker_quiet_on_fitting_line(tmp_path):
    svg = _write(tmp_path / 'svg_output' / 'a.svg', SVG_TMPL.format(
        body='<text x="60" y="20" font-size="19" '
             'font-family="Arial, sans-serif" fill="#000000">短文本</text>'))
    _write(tmp_path / 'spec_lock.md', LOCK_OK)
    checker = SVGQualityChecker()
    result = checker.check_file(str(svg))
    assert not [w for w in result['warnings'] if 'overflow' in w]


# ---------------------------------------------------------------- slides

def test_parse_slide_filter():
    from visual_review import parse_slide_filter
    assert parse_slide_filter(None) is None
    assert parse_slide_filter('') is None
    assert parse_slide_filter('1,8,14') == {1, 8, 14}
    assert parse_slide_filter('8-10') == {8, 9, 10}
    assert parse_slide_filter('1, 8-10') == {1, 8, 9, 10}
