import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_projection_manifest_maps_source_pages_to_svg_renderer(tmp_path: Path):
    from scripts.pptx_projection import build_projection_manifest, project_slide, write_projection_manifest

    workspace = tmp_path / "workspace"
    (workspace / "svg-flat").mkdir(parents=True)
    (workspace / "svg-flat" / "slide_01.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text data-pptx-textbox="true" data-pptx-box-x="10" data-pptx-box-y="10" data-pptx-box-w="100" data-pptx-box-h="40" x="60" y="30" font-size="20">Old</text></svg>',
        encoding="utf-8",
    )
    _write_json(workspace / "source_graph.json", {"schema_version": "easyslides.source_graph.v1", "status": "ready"})
    _write_json(workspace / "manifest.json", {"slides": [{"index": 1, "flatSvgFile": "slide_01.svg"}]})
    _write_json(workspace / "layout_spec.json", {"slides": [{"slide_id": "slide-01", "index": 1, "page_role": "cover", "spatial_contract": {"preserve_geometry": True}}]})
    _write_json(workspace / "component_catalog.json", {"components": [{"component_id": "pptx_shape_a", "classification": "replaceable", "instances": [{"part_id": "slide-01", "part_role": "slide"}], "slot_contract_ids": ["slot-title"]}]})
    _write_json(workspace / "slot_contracts.json", {"slots": [{"slot_id": "slot-title", "kind": "text", "geometry": {"x": 10, "y": 10, "width": 100, "height": 40}, "capacity": {"max_lines": 1}}]})

    payload = build_projection_manifest(template_id="fixture", source_workspace=workspace)
    write_projection_manifest(workspace, payload)
    output = tmp_path / "projected.svg"
    report = project_slide(source_workspace=workspace, slide_id="slide-01", values={"slot-title": "New"}, output_svg=output)

    assert payload["schema_version"] == "easyslides.pptx_projection_manifest.v1"
    assert payload["pages"][0]["renderer_id"] == "source_template_projection"
    assert payload["pages"][0]["status"] == "ready"
    assert payload["components"][0]["status"] == "ready"
    assert report["status"] == "pass"
    assert output.exists()


def test_fixed_components_are_protected_not_projection_reviews(tmp_path: Path):
    from scripts.pptx_projection import build_projection_manifest

    workspace = tmp_path / "workspace"
    (workspace / "svg-flat").mkdir(parents=True)
    (workspace / "svg-flat" / "slide_01.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" />', encoding="utf-8")
    _write_json(workspace / "source_graph.json", {"schema_version": "easyslides.source_graph.v1", "status": "ready"})
    _write_json(workspace / "manifest.json", {"slides": [{"index": 1, "flatSvgFile": "slide_01.svg"}]})
    _write_json(workspace / "layout_spec.json", {"slides": [{"slide_id": "slide-01", "index": 1, "page_role": "content"}]})
    _write_json(
        workspace / "component_catalog.json",
        {
            "components": [
                {
                    "component_id": "fixed-nav",
                    "classification": "fixed",
                    "instances": [{"part_id": "slide-01", "part_role": "slide"}],
                }
            ]
        },
    )
    _write_json(workspace / "slot_contracts.json", {"slots": []})

    payload = build_projection_manifest(template_id="fixture", source_workspace=workspace)

    assert payload["components"][0]["status"] == "protected"
    assert payload["components"][0]["targets"] == []
    assert payload["summary"]["review_required_count"] == 0
