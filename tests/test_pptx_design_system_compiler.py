import json
import tempfile
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _source_graph() -> dict:
    geometry = {
        "x": 96,
        "y": 96,
        "width": 384,
        "height": 48,
        "center_y": 120,
    }
    return {
        "schema_version": "easyslides.source_graph.v1",
        "status": "ready",
        "source": {"pptx": "fixture.pptx", "name": "fixture.pptx", "sha256": "fixture-sha"},
        "canvas": {"width_px": 1280, "height_px": 720},
        "themes": [{"path": "ppt/theme/theme1.xml", "theme": {"colors": {"accent1": "#1F4E79"}, "fonts": {"majorLatin": "Aptos Display"}}}],
        "parts": {
            "masters": [{"id": "master-01", "role": "master", "path": "ppt/slideMasters/slideMaster1.xml", "nodes": [], "used_by_slides": [1]}],
            "layouts": [{"id": "layout-01", "role": "layout", "path": "ppt/slideLayouts/slideLayout1.xml", "parent_id": "master-01", "nodes": [], "used_by_slides": [1]}],
            "slides": [{
                "id": "slide-01",
                "role": "slide",
                "index": 1,
                "path": "ppt/slides/slide1.xml",
                "layout_id": "layout-01",
                "master_id": "master-01",
                "nodes": [
                    {
                        "object_id": "ppt/slides/slide1.xml::shape:2",
                        "kind": "shape",
                        "shape_id": "2",
                        "name": "Title",
                        "order": 0,
                        "geometry": geometry,
                        "placeholder": {"type": "title", "idx": "1"},
                        "text": {"plain": "Title", "line_count": 1, "char_count": 5},
                        "text_layout": {"vertical_anchor": "ctr"},
                        "style": {"geometry_preset": "roundRect"},
                        "relationships": [],
                    },
                    {
                        "object_id": "ppt/slides/slide1.xml::picture:3",
                        "kind": "picture",
                        "shape_id": "3",
                        "name": "Figure",
                        "order": 1,
                        "geometry": {"x": 600, "y": 180, "width": 320, "height": 240, "center_y": 300},
                        "placeholder": None,
                        "text": None,
                        "text_layout": None,
                        "style": {},
                        "relationships": [{"attribute": "embed", "id": "rId2", "type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", "target": "ppt/media/image1.png"}],
                    },
                ],
            }],
        },
        "assets": [{"part_path": "ppt/media/image1.png", "name": "image1.png", "sha256": "image-sha", "referenced_by": ["slide-01"]}],
        "counts": {"masters": 1, "layouts": 1, "slides": 1, "nodes": 2, "assets": 1},
        "invariants": {"vertical_alignment": {"rule": "hard"}},
    }


def test_compiles_source_template_into_declarative_pack_and_registry_fragment():
    from scripts.component_registry import build_component_registry, validate_component_registry
    from scripts.pptx_design_system_compiler import compile_design_system_pack, write_design_system_pack
    from scripts.pptx_distill_registry import build_semantic_specs, write_semantic_specs

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "source_workspace"
        workspace.mkdir()
        graph = _source_graph()
        _write_json(workspace / "source_graph.json", graph)
        _write_json(workspace / "manifest.json", {"slides": [{"slidePath": "ppt/slides/slide1.xml", "index": 1, "pageType": "cover_candidate"}]})
        write_semantic_specs(
            workspace,
            build_semantic_specs(
                template_id="fixture",
                graph=graph,
                manifest={"slides": [{"slidePath": "ppt/slides/slide1.xml", "index": 1, "pageType": "cover_candidate"}]},
            ),
        )
        compiled = compile_design_system_pack(template_id="fixture", source_workspace=workspace)
        paths = write_design_system_pack(workspace, compiled)
        registry = build_component_registry(
            include_template_asset_bank=False,
            source_design_system_roots=[workspace],
        )
        report = validate_component_registry(registry)

        pack = json.loads(paths["design_system_pack"].read_text(encoding="utf-8"))
        fragment = json.loads(paths["component_registry_fragment"].read_text(encoding="utf-8"))

    assert report["status"] == "pass", report["issues"]
    assert pack["schema_version"] == "easyslides.pptx_design_system_pack.v1"
    assert pack["installability"] == "source_template_only"
    assert pack["promotion_status"] == "requires_renderer_mapping_and_cross_material_qa"
    assert fragment["schema_version"] == "easyslides.component_registry_fragment.v1"
    assert fragment["assets"]
    source_assets = [asset for asset in registry["assets"] if asset["granularity"] == "pptx_source_component"]
    assert source_assets
    assert source_assets[0]["render_backend"] == "source_template_projection"
    assert source_assets[0]["metadata"]["installability"] == "source_template_only"
    assert source_assets[0]["metadata"]["renderer_id"] == "source_template_projection"
