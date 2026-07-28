#!/usr/bin/env python3
"""Unified EasySlides command hub."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from workflow_manifest import main as workflow_manifest_main  # noqa: E402


DELEGATED_COMMANDS = {
    "project": "project_manager.py",
    "source-to-md": "source_to_md.py",
    "distill": "pptx_template_distill.py",
    "semantic-render": "semantic_template_renderer.py",
    "template-gate": "template_production_gate.py",
    "template-visual-invariants": "template_visual_invariants.py",
    "template-fill": "template_fill_pptx.py",
    "enhance": "native_enhance_pptx.py",
    "beautify": "beautify_pptx.py",
    "review": "visual_review.py",
    "brand": "create_brand.py",
    "confirm": "confirm_ui.py",
    "clarify": "clarification_gate.py",
    "component": "component_pack.py",
    "component-market": "component_marketplace.py",
    "component-workflow": "component_workflow.py",
    "renderer-governance": "renderer_governance.py",
    "cross-renderer-regression": "cross_renderer_visual_regression.py",
    "chart": "chart_library.py",
    "icon": "icon_library.py",
    "content-contract": "content_plan_contract.py",
    "design-contract": "design_plan_contract.py",
    "deck-gates": "deck_gates.py",
    "review-contract": "review_contract.py",
    "template-package": "template_package.py",
    "template-capabilities": "template_capabilities.py",
    "template-compile": "template_compiler.py",
    "slide-compile": "slide_compiler.py",
    "plan": "presentation_plan_builder.py",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EasySlides command hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Product commands:\n"
            "  project       Project creation, source import, validation\n"
            "  source-to-md  Convert files, directories, or URLs to Markdown\n"
            "  distill       Distill PPTX evidence and gated template assets\n"
            "  semantic-render Render a named-slot semantic template\n"
            "  template-gate Fail-closed semantic template production gate\n"
            "  template-visual-invariants Validate declared text-centre and mirror invariants\n"
            "  template-fill Native PPTX template library fill\n"
            "  enhance       Native append-only PPTX notes/audio/timing enhancement\n"
            "  beautify      Conservative 1:1 PPTX beautification\n"
            "  review        Visual review package generation\n"
            "  brand         Brand preset creation and inspection\n"
            "  confirm       Confirmation page generation\n"
            "  clarify       Blocking user-choice clarification gate\n"
            "  component     Declarative component pack validation and installation\n"
            "  component-market Search and install verified declarative component packs\n"
            "  component-workflow Build a component plan, choice review, gallery, and PPTX preview\n"
            "  renderer-governance Verify repository-owned SVG/PPTX renderer contracts\n"
            "  cross-renderer-regression Compare native PowerPoint and LibreOffice rendering\n"
            "  chart         PPT Master-compatible chart asset catalog and lookup\n"
            "  icon          Icon family catalog, semantic lookup, and project sync\n"
            "  content-contract Validate source-facing content_plan.json\n"
            "  design-contract Validate design-facing design_plan.json\n"
            "  deck-gates    Fail-closed deck delivery and handoff gate\n"
            "  review-contract Validate independent critic/arbiter reports\n"
            "  template-package Create, validate, and register reusable template packages\n"
            "  template-capabilities Validate and synchronize per-template composition boundaries\n"
            "  template-compile Compile canonical template sources into Template IR\n"
            "  slide-compile Resolve shell, body variant, components, and render Slide IR\n"
            "  plan          Build draft content/design plan scaffolds\n"
            "  workflow      Workflow manifest utilities\n\n"
            "Run `python scripts/easyslides.py <command> --help` for command-specific help."
        ),
    )
    parser.add_argument("command", nargs="?", help="Command to run.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the command.")
    return parser


def _delegate(command: str, args: list[str]) -> int:
    script = SCRIPTS_DIR / DELEGATED_COMMANDS[command]
    return subprocess.run([sys.executable, str(script), *args], cwd=SCRIPTS_DIR.parent).returncode


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        build_parser().print_help()
        return 0

    command, rest = argv[0], argv[1:]
    if command in DELEGATED_COMMANDS:
        return _delegate(command, rest)
    if command == "workflow":
        return workflow_manifest_main(rest)

    parser = build_parser()
    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
