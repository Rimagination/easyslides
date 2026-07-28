#!/usr/bin/env python3
"""Expose the PPT Master-compatible chart SVGs as productized assets.

The SVG files remain the visual source of truth. This adapter adds the stable
metadata that EasySlides needs for discovery, planning, payload validation, and
future renderer upgrades without duplicating the 71-template catalog.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHARTS_ROOT = ROOT / "templates" / "charts"
CHART_INDEX_PATH = CHARTS_ROOT / "charts_index.json"
SCHEMA_VERSION = "easyslides.chart_library.v1"
REPORT_SCHEMA_VERSION = "easyslides.chart_library_report.v1"


QUANTITATIVE = {
    "area_chart",
    "bar_chart",
    "box_plot_chart",
    "bubble_chart",
    "bullet_chart",
    "butterfly_chart",
    "donut_chart",
    "dual_axis_line_chart",
    "dumbbell_chart",
    "funnel_chart",
    "gauge_chart",
    "grouped_bar_chart",
    "heatmap_chart",
    "horizontal_bar_chart",
    "line_chart",
    "pareto_chart",
    "pie_chart",
    "progress_bar_chart",
    "radar_chart",
    "sankey_chart",
    "scatter_chart",
    "stacked_area_chart",
    "stacked_bar_chart",
    "treemap_chart",
    "waterfall_chart",
    "word_cloud",
}
TABLES = {
    "basic_table",
    "comparison_table",
    "consulting_table",
    "feature_matrix_table",
    "financial_statement_table",
    "harvey_balls_table",
    "project_schedule_table",
}
WORKFLOW = {
    "circular_stages",
    "chevron_chain_with_tail",
    "chevron_process",
    "gantt_chart",
    "journey_map",
    "numbered_steps",
    "pipeline_with_stages",
    "process_flow",
    "roadmap_vertical",
    "snake_flow",
    "timeline",
}
FRAMEWORK = {
    "concentric_circles",
    "fishbone_diagram",
    "hub_inward_arrows",
    "hub_spoke",
    "matrix_2x2",
    "mind_map",
    "pros_cons_chart",
    "quadrant_bubble_scatter",
    "quadrant_text_bullets",
    "segmented_wheel",
    "venn_diagram",
}
STRUCTURAL = {
    "agenda_list",
    "arc_anchored_list",
    "client_server_flow",
    "comparison_columns",
    "comparison_table",
    "icon_grid",
    "isometric_stairs",
    "labeled_card",
    "layered_architecture",
    "module_composition",
    "pyramid_chart",
    "pyramid_isometric",
    "team_roster",
    "top_down_tree",
    "vertical_list",
    "vertical_pillars",
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _family(chart_id: str) -> str:
    if chart_id in QUANTITATIVE:
        return "quantitative"
    if chart_id in TABLES:
        return "table"
    if chart_id in WORKFLOW:
        return "workflow"
    if chart_id in FRAMEWORK:
        return "framework"
    if chart_id in STRUCTURAL:
        return "structural"
    return "diagram"


def _content_shapes(chart_id: str, family: str) -> list[str]:
    shapes: set[str] = {"chart"}
    if family == "quantitative":
        shapes.add("quantitative_evidence")
    elif family == "table":
        shapes.update({"matrix", "table"})
    elif family == "workflow":
        shapes.update({"workflow", "sequence"})
    elif family == "framework":
        shapes.update({"framework", "matrix"})
    else:
        shapes.add("parallel_points")

    if chart_id in {"line_chart", "area_chart", "dual_axis_line_chart", "stacked_area_chart", "timeline", "roadmap_vertical", "gantt_chart"}:
        shapes.add("trend_or_time")
    if chart_id in {"bar_chart", "grouped_bar_chart", "horizontal_bar_chart", "butterfly_chart", "dumbbell_chart", "comparison_columns", "comparison_table"}:
        shapes.add("comparison")
    if chart_id in {"pie_chart", "donut_chart", "treemap_chart", "stacked_bar_chart", "stacked_area_chart"}:
        shapes.add("composition")
    if chart_id in {"process_flow", "pipeline_with_stages", "chevron_process", "chevron_chain_with_tail", "funnel_chart", "sankey_chart", "snake_flow", "circular_stages"}:
        shapes.add("causal_chain")
    if chart_id in {"scatter_chart", "bubble_chart", "quadrant_bubble_scatter", "matrix_2x2", "heatmap_chart", "radar_chart"}:
        shapes.add("matrix")
    return sorted(shapes)


def _page_roles(family: str, chart_id: str) -> list[str]:
    if family == "quantitative":
        return ["overview", "result"]
    if family == "table":
        return ["comparison", "result"]
    if family == "workflow":
        return ["method", "content"]
    if chart_id in {"agenda_list", "vertical_list", "labeled_card", "icon_grid"}:
        return ["overview", "content"]
    return ["comparison", "content", "method"]


def _data_model(family: str, chart_id: str) -> str:
    if family == "table":
        return "cell_grid"
    if family == "workflow":
        return "ordered_nodes"
    if family == "framework":
        return "labeled_regions"
    if chart_id in {"scatter_chart", "bubble_chart", "quadrant_bubble_scatter", "heatmap_chart"}:
        return "xy_or_matrix"
    if family == "quantitative":
        return "category_series"
    return "labeled_items"


def _selection(summary: str, family: str, chart_id: str) -> dict[str, Any]:
    return {
        "content_shapes": _content_shapes(chart_id, family),
        "page_roles": _page_roles(family, chart_id),
        "density": "high" if family == "table" else "medium",
        "best_for": summary,
    }


def _slots(family: str) -> list[dict[str, Any]]:
    slots = [
        {
            "slot_id": "title",
            "kind": "text",
            "role": "title",
            "required": False,
            "alignment": {"horizontal": "left", "vertical": "middle"},
        },
        {
            "slot_id": "data",
            "kind": "data",
            "role": "chart_data",
            "required": True,
        },
    ]
    if family in {"quantitative", "table"}:
        slots.append({"slot_id": "unit", "kind": "text", "role": "unit_label", "required": False})
    return slots


def _normalize_chart(chart_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    summary = str(spec.get("summary") or "").strip()
    family = _family(chart_id)
    return {
        "chart_id": chart_id,
        "asset_id": f"chart/{chart_id}",
        "family": family,
        "summary": summary,
        "selection": _selection(summary, family, chart_id),
        "asset_path": _relative(CHARTS_ROOT / f"{chart_id}.svg"),
        "render_backend": "svg_template",
        "renderer_id": "chart_svg_template",
        "editability": "svg_text_slots",
        "native_support": "separate_native_backend",
        "data_model": _data_model(family, chart_id),
        "slots": _slots(family),
        "required_gates": [
            "component_plan_contract",
            "chart_asset_contract",
            "chart_text_slots",
            "visual_measure_gate",
        ],
        "upstream": {
            "project": "hugohe3/ppt-master",
            "compatibility": "ppt-master-chart-template",
        },
    }


def load_chart_library(index_path: str | Path | None = None) -> dict[str, Any]:
    """Load and normalize the PPT Master-compatible chart catalog."""
    path = Path(index_path) if index_path else CHART_INDEX_PATH
    payload = _read_json(path)
    raw_charts = payload.get("charts")
    if not isinstance(raw_charts, dict):
        raise ValueError("charts_index.json must define a charts object")
    charts = [
        _normalize_chart(str(chart_id), spec)
        for chart_id, spec in raw_charts.items()
        if isinstance(spec, dict) and str(chart_id).strip()
    ]
    charts.sort(key=lambda item: item["chart_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "library_id": "ppt-master-compatible-charts",
        "source_index": _relative(path),
        "upstream": "hugohe3/ppt-master",
        "declared_total": int((payload.get("meta") or {}).get("total", len(charts))),
        "chart_count": len(charts),
        "charts": charts,
    }


def validate_chart_library(library: dict[str, Any] | None = None) -> dict[str, Any]:
    library = library or load_chart_library()
    issues: list[dict[str, str]] = []
    charts = library.get("charts")
    if library.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "CHART-LIBRARY-SCHEMA", "message": "unexpected chart library schema"})
    if not isinstance(charts, list) or not charts:
        issues.append({"code": "CHART-LIBRARY-EMPTY", "message": "charts must be a non-empty list"})
        charts = []
    seen: set[str] = set()
    for index, chart in enumerate(charts):
        prefix = f"charts[{index}]"
        if not isinstance(chart, dict):
            issues.append({"code": "CHART-LIBRARY-ITEM", "message": f"{prefix} must be an object"})
            continue
        chart_id = str(chart.get("chart_id") or "")
        if not chart_id:
            issues.append({"code": "CHART-LIBRARY-ID", "message": f"{prefix}.chart_id is required"})
        elif chart_id in seen:
            issues.append({"code": "CHART-LIBRARY-DUPLICATE", "message": f"duplicate chart_id {chart_id}"})
        seen.add(chart_id)
        asset_path = ROOT / str(chart.get("asset_path") or "")
        if not asset_path.is_file():
            issues.append({"code": "CHART-LIBRARY-ASSET", "message": f"missing SVG asset for {chart_id}"})
        for key in ("family", "summary", "selection", "slots", "required_gates"):
            if key not in chart:
                issues.append({"code": "CHART-LIBRARY-FIELD", "message": f"{prefix}.{key} is required"})
    declared_total = int(library.get("declared_total") or 0)
    if declared_total and declared_total != len(charts):
        issues.append({"code": "CHART-LIBRARY-COUNT", "message": f"declared total {declared_total} != actual {len(charts)}"})
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "issue_count": len(issues),
        "issues": issues,
        "chart_count": len(charts),
    }


def search_charts(
    query: str = "",
    *,
    family: str | None = None,
    content_shape: str | None = None,
    limit: int = 10,
    library: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    terms = [term.lower() for term in query.split() if term.strip()]
    rows: list[tuple[int, dict[str, Any]]] = []
    for chart in (library or load_chart_library()).get("charts", []):
        if family and chart.get("family") != family:
            continue
        selection = chart.get("selection") if isinstance(chart.get("selection"), dict) else {}
        if content_shape and content_shape not in selection.get("content_shapes", []):
            continue
        haystack = " ".join(
            [
                str(chart.get("chart_id") or ""),
                str(chart.get("family") or ""),
                str(chart.get("summary") or ""),
                json.dumps(selection, ensure_ascii=False),
            ]
        ).lower()
        score = sum(2 if term in str(chart.get("chart_id") or "").lower() else 1 for term in terms if term in haystack)
        if terms and score == 0:
            continue
        rows.append((score, chart))
    rows.sort(key=lambda row: (-row[0], row[1]["chart_id"]))
    return [chart for _, chart in rows[: max(limit, 0)]]


def validate_chart_payload(chart_id: str, payload: dict[str, Any], library: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the minimum data envelope without constraining chart-specific data."""
    chart_ids = {chart["chart_id"] for chart in (library or load_chart_library()).get("charts", [])}
    violations: list[dict[str, str]] = []
    if chart_id not in chart_ids:
        violations.append({"code": "CHART-PAYLOAD-ID", "message": f"unknown chart_id {chart_id!r}"})
    if payload and not any(key in payload for key in ("data", "series", "items", "values", "svg")):
        violations.append({"code": "CHART-PAYLOAD-DATA", "message": "chart payload needs data, series, items, values, or svg"})
    return {
        "passed": not violations,
        "violations": violations,
        "checked_slots": 1 if payload else 0,
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the EasySlides chart asset library.")
    parser.add_argument("--index", default=str(CHART_INDEX_PATH))
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--family")
    list_parser.add_argument("--content-shape")
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query", nargs="?", default="")
    search_parser.add_argument("--family")
    search_parser.add_argument("--content-shape")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("chart_id")
    inspect_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    library = load_chart_library(args.index)
    if args.command == "validate":
        report = validate_chart_library(library)
        if args.json:
            _print_json(report)
        else:
            print(f"Chart library: {report['status']} ({report['issue_count']} issue(s), {report['chart_count']} charts)")
        return 0 if report["status"] == "pass" else 1

    if args.command == "inspect":
        chart = next((item for item in library["charts"] if item["chart_id"] == args.chart_id), None)
        if chart is None:
            return 1
        if args.json:
            _print_json(chart)
        else:
            print(f"{chart['chart_id']}\t{chart['family']}\t{chart['summary']}")
        return 0

    if args.command == "list":
        rows = search_charts(family=args.family, content_shape=args.content_shape, limit=args.limit, library=library)
    else:
        rows = search_charts(args.query, family=args.family, content_shape=args.content_shape, limit=args.limit, library=library)
    if args.json:
        _print_json({"schema_version": SCHEMA_VERSION, "matches": rows, "match_count": len(rows)})
    else:
        for chart in rows:
            print(f"{chart['chart_id']}\t{chart['family']}\t{chart['summary']}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
