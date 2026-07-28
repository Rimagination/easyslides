import json
import tempfile
import unittest
import zipfile
from pathlib import Path


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _write_pptx(path: Path) -> None:
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>""",
        "ppt/presentation.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId2"/></p:sldMasterIdLst>
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000"/>
</p:presentation>""",
        "ppt/_rels/presentation.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
</Relationships>""",
        "ppt/slides/slide1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:cSld name="Slide 1"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr/>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title" idx="1"/></p:nvPr></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="3657600" cy="914400"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="1F4E79"/></a:solidFill></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2400"><a:latin typeface="Aptos Display"/></a:rPr><a:t>Title evidence</a:t></a:r><a:endParaRPr sz="2400"/></a:p></p:txBody>
    </p:sp>
    <p:pic>
      <p:nvPicPr><p:cNvPr id="3" name="Figure 1"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr><a:xfrm><a:off x="4572000" y="2286000"/><a:ext cx="3657600" cy="2286000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
    </p:pic>
  </p:spTree></p:cSld>
</p:sld>""",
        "ppt/slides/_rels/slide1.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>""",
        "ppt/slideLayouts/slideLayout1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sldLayout xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" type="title" name="Title Layout">
  <p:cSld name="Title Layout"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
    <p:sp><p:nvSpPr><p:cNvPr id="2" name="Layout Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title" idx="1"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="10058400" cy="914400"/></a:xfrm></p:spPr></p:sp>
  </p:spTree></p:cSld>
</p:sldLayout>""",
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>""",
        "ppt/slideMasters/slideMaster1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sldMaster xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:cSld name="Master"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
    <p:sp><p:nvSpPr><p:cNvPr id="2" name="Master Rail"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="457200" cy="6858000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></p:spPr></p:sp>
  </p:spTree></p:cSld>
  <p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>""",
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>""",
        "ppt/theme/theme1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<a:theme xmlns:a="{A_NS}" name="Fixture"><a:themeElements><a:clrScheme name="Fixture"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1><a:accent1><a:srgbClr val="1F4E79"/></a:accent1></a:clrScheme><a:fontScheme name="Fixture"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme></a:themeElements></a:theme>""",
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("ppt/media/image1.png", b"fixture-image")


class PptxSourceGraphTests(unittest.TestCase):
    def test_builds_native_lineage_objects_and_asset_provenance(self):
        from scripts.pptx_source_graph import build_source_graph

        with tempfile.TemporaryDirectory() as tmp:
            pptx_path = Path(tmp) / "fixture.pptx"
            _write_pptx(pptx_path)
            graph = build_source_graph(pptx_path)

        self.assertEqual(graph["schema_version"], "easyslides.source_graph.v1")
        self.assertEqual(graph["status"], "ready")
        self.assertEqual(graph["counts"], {"masters": 1, "layouts": 1, "slides": 1, "nodes": 4, "assets": 1})
        self.assertEqual(graph["canvas"]["width_px"], 1280)
        self.assertEqual(graph["canvas"]["height_px"], 720)
        slide = graph["parts"]["slides"][0]
        self.assertEqual(slide["layout_id"], "layout-01")
        self.assertEqual(slide["master_id"], "master-01")
        title = next(node for node in slide["nodes"] if node["shape_id"] == "2")
        self.assertEqual(title["text"]["plain"], "Title evidence")
        self.assertEqual(title["placeholder"]["type"], "title")
        self.assertEqual(title["geometry"]["center_y"], 144)
        picture = next(node for node in slide["nodes"] if node["kind"] == "picture")
        self.assertEqual(picture["relationships"][0]["target"], "ppt/media/image1.png")
        self.assertEqual(graph["assets"][0]["referenced_by"], ["slide-01"])
        self.assertEqual(graph["themes"][0]["theme"]["colors"]["accent1"], "#1F4E79")
        self.assertTrue(graph["invariants"]["vertical_alignment"]["eligible_text_center_y_equals_container_center_y"])

    def test_distill_manifest_declares_phase_outputs_and_modes(self):
        from scripts.pptx_source_graph import build_distill_manifest

        graph = {
            "status": "ready",
            "source": {"sha256": "abc"},
            "counts": {"slides": 1},
            "invariants": {"vertical_alignment": {"rule": "hard"}},
        }
        manifest = build_distill_manifest(
            template_id="fixture",
            source_workspace=Path("tmp/source"),
            source_pptx=Path("tmp/source.pptx"),
            source_graph=graph,
        )

        self.assertEqual(manifest["schema_version"], "easyslides.distill_manifest.v1")
        self.assertEqual(manifest["stage"], "phase_2_semantic_registry")
        self.assertEqual(manifest["artifacts"]["source_graph"], "source_graph.json")
        self.assertEqual(manifest["supported_modes"], ["mirror", "layout", "design-system"])
        self.assertIn("component_catalog", manifest["artifacts"])

    def test_cli_writes_json_output(self):
        from scripts.pptx_source_graph import main

        with tempfile.TemporaryDirectory() as tmp:
            pptx_path = Path(tmp) / "fixture.pptx"
            output_path = Path(tmp) / "graph.json"
            _write_pptx(pptx_path)
            exit_code = main([str(pptx_path), "--output", str(output_path)])
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ready")

    def test_phase_two_registers_identity_layout_components_and_slots(self):
        from scripts.pptx_distill_registry import build_semantic_specs
        from scripts.pptx_source_graph import build_source_graph

        with tempfile.TemporaryDirectory() as tmp:
            pptx_path = Path(tmp) / "fixture.pptx"
            _write_pptx(pptx_path)
            graph = build_source_graph(pptx_path)
            specs = build_semantic_specs(
                template_id="fixture",
                graph=graph,
                manifest={"slides": [{"slidePath": "ppt/slides/slide1.xml", "index": 1, "pageType": "cover_candidate"}]},
            )

        self.assertEqual(specs["identity_spec"]["theme"]["colors"]["accent1"], "#1F4E79")
        self.assertEqual(specs["layout_spec"]["slides"][0]["page_role"], "cover")
        self.assertGreaterEqual(len(specs["component_catalog"]["components"]), 3)
        self.assertIn("component_candidates", specs)
        self.assertTrue(all("text_center_y_matches_container_center_y" in row["promotion_requirements"] for row in specs["component_candidates"]["candidates"]))
        slots = specs["slot_contracts"]["slots"]
        self.assertEqual({slot["role"] for slot in slots}, {"title", "image"})
        self.assertTrue(all(slot["alignment"]["center_lock"] for slot in slots if slot["kind"] == "text"))
        self.assertEqual(specs["slot_contracts"]["validation"]["status"], "pass")
        self.assertEqual(specs["review_queue"]["status"], "clear")
        self.assertEqual(specs["adaptation_policy"]["hard_rules"][0]["severity"], "error")
