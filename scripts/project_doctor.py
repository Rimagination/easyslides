#!/usr/bin/env python3
"""One-shot project health check for EasySlides decks.

Runs every contract the pipeline enforces — in read-only fashion, before you
commit to generation or after a failure — and prints a single human-readable
report: what's fine, what's broken, where to fix it.

Usage:
    python scripts/project_doctor.py <project_path> [--json]

Checks:
    1. Structure        deck_plan.json / clarification_request.json /
                        spec_lock.md / sources/ / svg_output/ present
    2. Clarification    request exists and is confirmed (pipeline entry gate)
    3. Deck plan        deck_plan_contract validation (story contract)
    4. Spec lock        parseable; canvas/colors/typography(body)/page_rhythm
                        sections present; rhythm keys match deck plan pages
    5. Icons            every <use data-icon> ref in svg_output/ resolves on
                        disk; declared library matches the refs in use
    6. SVG quality      svg_quality_checker run (errors only summarized here)

Exit code 0 when no ERROR-level findings, 1 otherwise. Warnings don't fail.
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []  # (level, check, detail)

    def ok(self, check: str, detail: str = '') -> None:
        self.rows.append(('OK', check, detail))

    def warn(self, check: str, detail: str) -> None:
        self.rows.append(('WARN', check, detail))

    def error(self, check: str, detail: str) -> None:
        self.rows.append(('ERROR', check, detail))

    @property
    def has_errors(self) -> bool:
        return any(level == 'ERROR' for level, _, _ in self.rows)

    def print(self) -> None:
        icon = {'OK': '  ✓ ', 'WARN': '  ⚠ ', 'ERROR': '  ✗ '}
        last_check = None
        for level, check, detail in self.rows:
            if check != last_check:
                print(f"[{check}]")
                last_check = check
            print(f"{icon[level]}{detail}" if detail else f"{icon[level]}{check}")
        errors = sum(1 for level, _, _ in self.rows if level == 'ERROR')
        warns = sum(1 for level, _, _ in self.rows if level == 'WARN')
        print()
        print(f"Result: {'FAIL' if errors else 'PASS'} "
              f"({errors} error(s), {warns} warning(s))")


def check_structure(project: Path, report: Report) -> None:
    required = {
        'deck_plan.json': project / 'deck_plan.json',
        'spec_lock.md': project / 'spec_lock.md',
        'sources/': project / 'sources',
        'svg_output/': project / 'svg_output',
    }
    for label, path in required.items():
        if path.exists():
            report.ok('structure', f'{label} present')
        else:
            report.error('structure', f'{label} missing at {path}')
    clarify = project / 'clarification_request.json'
    if clarify.exists():
        report.ok('structure', 'clarification_request.json present')
    else:
        report.warn('structure',
                    'clarification_request.json missing — pipeline entry gate '
                    'unrecorded (generation is not authorized without it)')


def check_clarification(project: Path, report: Report) -> None:
    path = project / 'clarification_request.json'
    if not path.exists():
        return
    try:
        from clarification_gate import require_confirmed
        request = require_confirmed(path)
        report.ok('clarification',
                  f"status={request.get('status')}, route={request.get('route')}")
    except Exception as exc:
        report.error('clarification', f'not confirmed: {exc}')


def check_deck_plan(project: Path, report: Report) -> int | None:
    path = project / 'deck_plan.json'
    if not path.exists():
        return None
    try:
        from deck_plan_contract import validate_deck_plan
        plan = json.loads(path.read_text(encoding='utf-8'))
        report_ = validate_deck_plan(plan, repo_root=REPO_ROOT)
        if report_.get('status') == 'pass':
            report.ok('deck-plan',
                      f"contract pass, {report_.get('slide_count')} slides")
        else:
            for issue in report_.get('issues', [])[:10]:
                report.error('deck-plan',
                             f"{issue.get('code')}: {issue.get('message')} "
                             f"({issue.get('path') or ''})")
        return len(plan.get('slides', []))
    except Exception as exc:
        report.error('deck-plan', f'validation crashed: {exc}')
        return None


def check_spec_lock(project: Path, report: Report, page_count: int | None) -> None:
    path = project / 'spec_lock.md'
    if not path.exists():
        return
    try:
        from update_spec import parse_lock
        lock = parse_lock(path)
    except Exception as exc:
        report.error('spec-lock', f'unparseable: {exc}')
        return
    for section in ('canvas', 'colors', 'typography'):
        if section in lock:
            report.ok('spec-lock', f'[{section}] present')
        else:
            report.error('spec-lock', f'[{section}] section missing')
    typo = lock.get('typography', {})
    if not typo.get('body'):
        report.error('spec-lock',
                     'typography.body missing — it is the ramp baseline; '
                     'font-size drift checks cannot work without it')
    rhythm = lock.get('page_rhythm', {})
    if not rhythm:
        report.warn('spec-lock',
                    '[page_rhythm] missing — executor defaults every page to '
                    'dense (the "every page looks the same" look)')
    elif page_count is not None and len(rhythm) != page_count:
        report.warn('spec-lock',
                    f'[page_rhythm] has {len(rhythm)} entries but deck plan '
                    f'has {page_count} slides')
    icons = lock.get('icons', {})
    if icons.get('library'):
        report.ok('spec-lock',
                  f"icon library declared: {icons['library']}")


def check_icons(project: Path, report: Report) -> None:
    svg_dir = project / 'svg_output'
    if not svg_dir.is_dir():
        return
    try:
        from svg_finalize.embed_icons import resolve_icon_path
    except ImportError:
        report.warn('icons', 'embed_icons unavailable — check skipped')
        return
    icons_dir = REPO_ROOT / 'templates' / 'icons'
    refs: dict[str, set[str]] = {}
    for svg in sorted(svg_dir.glob('*.svg')):
        text = svg.read_text(encoding='utf-8', errors='replace')
        for name in re.findall(r'data-icon="([^"]+)"', text):
            refs.setdefault(name, set()).add(svg.name)
    if not refs:
        report.ok('icons', 'no icon references')
        return
    missing = {n for n in refs
               if not resolve_icon_path(n, icons_dir)[0].exists()}
    libs_used = {n.split('/', 1)[0] for n in refs if '/' in n}
    for name in sorted(missing):
        users = sorted(refs[name])
        report.error('icons',
                     f'{name} missing on disk (used in {", ".join(users[:3])}'
                     f'{"…" if len(users) > 3 else ""}) — export would fail')
    if not missing:
        report.ok('icons', f'{len(refs)} distinct refs all resolve')
    declared = None
    lock_path = project / 'spec_lock.md'
    if lock_path.exists():
        try:
            from update_spec import parse_lock
            declared = parse_lock(lock_path).get('icons', {}).get('library')
        except Exception:
            pass
    if declared and len(libs_used) == 1 and libs_used != {declared}:
        report.warn('icons',
                    f'spec_lock declares library "{declared}" but refs use '
                    f'"{next(iter(libs_used))}" — one-library rule violated')


def check_svg_quality(project: Path, report: Report) -> None:
    svg_dir = project / 'svg_output'
    if not svg_dir.is_dir():
        return
    try:
        from svg_quality_checker import SVGQualityChecker
    except ImportError:
        report.warn('svg-quality', 'checker unavailable — check skipped')
        return
    checker = SVGQualityChecker()
    error_files = []
    for svg in sorted(svg_dir.glob('*.svg')):
        result = checker.check_file(str(svg))
        if not result['passed']:
            error_files.append((result['file'], result['errors'][:2]))
    if error_files:
        for name, errors in error_files:
            report.error('svg-quality', f'{name}: {errors[0]}')
    else:
        report.ok('svg-quality',
                  f'{checker.summary["total"]} SVG file(s), 0 errors')


def main() -> None:
    parser = argparse.ArgumentParser(description='EasySlides project doctor.')
    parser.add_argument('project', help='Project directory path.')
    parser.add_argument('--json', action='store_true', dest='as_json',
                        help='Machine-readable report.')
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        print(f"[ERROR] project not found: {project}")
        sys.exit(1)

    report = Report()
    report.ok('project', str(project))
    check_structure(project, report)
    check_clarification(project, report)
    page_count = check_deck_plan(project, report)
    check_spec_lock(project, report, page_count)
    check_icons(project, report)
    check_svg_quality(project, report)

    if args.as_json:
        print(json.dumps(
            {'project': str(project),
             'rows': [{'level': lv, 'check': ck, 'detail': dt}
                      for lv, ck, dt in report.rows]},
            ensure_ascii=False, indent=2))
    else:
        report.print()
    sys.exit(1 if report.has_errors else 0)


if __name__ == '__main__':
    main()
