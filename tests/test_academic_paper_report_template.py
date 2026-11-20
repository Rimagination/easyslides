import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scripts.semantic_template_renderer import (
    SemanticTemplateError,
    SlotCapacityError,
    load_template,
    render_deck,
    resolve_layout,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "layouts" / "academic_general"
EXAMPLE = TEMPLATE / "examples" / "deck_plan.json"


def example_plan():
    plan = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    plan["slides"][5]["slot_payload"]["FIGURE"] = str(TEMPLATE / "assets" / "example_figure.png")
    return plan


def write_plan(root, plan):
    path = root / "plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def slot_text(path, slot_id):
    root = ET.parse(path).getroot()
    matches = [node for node in root.iter() if node.get("data-slot") == slot_id]
    return ["".join(node.itertext()) for node in matches]


class AcademicPaperReportTemplateTests(unittest.TestCase):
    def test_former_template_paths_load_the_same_canonical_pack(self):
        for relative in ("templates/layouts/academic_paper", "templates/layouts/academic_paper_report",
                         "templates/development/academic_paper_report"):
            with self.subTest(path=relative):
                template = load_template(ROOT / relative)
                self.assertEqual(template.root, TEMPLATE.resolve())
                self.assertEqual(template.template_id, "academic_general")

    def test_former_paths_work_in_a_clean_checkout_and_preserve_existing_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "templates/layouts/academic_general"
            canonical.mkdir(parents=True)
            for filename in ("layouts.json", "body_variants.json"):
                shutil.copyfile(TEMPLATE / filename, canonical / filename)
            for row in json.loads((canonical / "layouts.json").read_text(encoding="utf-8"))["layouts"]:
                (canonical / row["svg"]).touch()
            for relative in ("templates/layouts/academic_paper", "templates/layouts/academic_paper_report",
                             "templates/development/academic_paper_report"):
                legacy = root / relative
                self.assertFalse(legacy.exists())
                self.assertEqual(load_template(legacy).root, canonical)
            custom = root / "templates/layouts/academic_paper_report"
            shutil.copytree(canonical, custom)
            self.assertEqual(load_template(custom).root, custom)

    def test_cover_can_omit_presenter_without_an_empty_badge(self):
        plan = {"theme_palette": "academic_green", "discipline_code": "07", "slides": [
            {"role": "cover", "layout_id": "cover_blue_band", "slot_payload": {
                "TITLE": "研究汇报", "BAND_IMAGE": ""
            }}
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "svg_output")
            root = ET.parse(work / "svg_output" / result["assignments"][0]["svg"]).getroot()
            self.assertFalse(any(n.get("id") == "reporter-pill" or n.get("data-slot") == "REPORTER"
                                 for n in root.iter()))

    def test_ending_resolves_presenter_logo_or_preserves_neutral_mark(self):
        plan = json.loads((TEMPLATE / "examples" / "ending_blue_band.json").read_text(encoding="utf-8"))
        plan["presenter_institution"] = "浙江大学"

        def fake_fetch(project, institution, *, variant, timeout):
            self.assertEqual((institution, variant), ("浙江大学", "emblem"))
            path = Path(project) / "assets" / "logos" / "test_emblem.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATE / "assets" / "example_figure.png", path)
            return {"status": "resolved", "reason": "exact_institution_match",
                    "asset_path": "assets/logos/test_emblem.png", "metadata": {"id": "test-university"}}

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with patch("scripts.semantic_template_renderer.fetch_logo", side_effect=fake_fetch) as fetch:
                result = render_deck(TEMPLATE, write_plan(work, plan), work / "auto" / "svg_output")
                fetch.assert_called_once()
            self.assertEqual(result["institution_logo"]["status"], "resolved")
            self.assertEqual(result["institution_logo"]["identity"]["institution"], "浙江大学")
            svg = work / "auto" / "svg_output" / result["assignments"][0]["svg"]
            root = ET.parse(svg).getroot()
            self.assertFalse(any(node.get("id") == "ending-neutral-mark" for node in root.iter()))
            logo = next(node for node in root.iter() if node.get("data-slot") == "INSTITUTION_LOGO")
            self.assertTrue(logo.get("href").endswith("test_emblem.png"))
            self.assertEqual(logo.get("preserveAspectRatio"), "xMidYMid meet")

            plan["metadata"] = {"institution": "清华大学"}
            with patch("scripts.semantic_template_renderer.fetch_logo") as fetch:
                result = render_deck(TEMPLATE, write_plan(work, plan), work / "ambiguous" / "svg_output")
                fetch.assert_not_called()
            self.assertEqual(result["institution_logo"]["reason"], "conflicting_presenter_affiliations")
            root = ET.parse(work / "ambiguous" / "svg_output" / result["assignments"][0]["svg"]).getroot()
            self.assertTrue(any(node.get("id") == "ending-neutral-mark" for node in root.iter()))

            del plan["metadata"]
            with patch("scripts.semantic_template_renderer.fetch_logo", return_value={
                "status": "fallback", "reason": "image_unavailable", "asset_path": None
            }) as fetch:
                result = render_deck(TEMPLATE, write_plan(work, plan), work / "missing" / "svg_output")
                fetch.assert_called_once()
            self.assertEqual(result["institution_logo"]["reason"], "image_unavailable")
            root = ET.parse(work / "missing" / "svg_output" / result["assignments"][0]["svg"]).getroot()
            self.assertTrue(any(node.get("id") == "ending-neutral-mark" for node in root.iter()))

            plan["slides"][0]["slot_payload"]["INSTITUTION_LOGO"] = ""
            with patch("scripts.semantic_template_renderer.fetch_logo") as fetch:
                result = render_deck(TEMPLATE, write_plan(work, plan), work / "disabled" / "svg_output")
                fetch.assert_not_called()
            root = ET.parse(work / "disabled" / "svg_output" / result["assignments"][0]["svg"]).getroot()
            self.assertTrue(any(node.get("id") == "ending-neutral-mark" for node in root.iter()))

            plan["slides"][0]["slot_payload"]["INSTITUTION_LOGO"] = str(TEMPLATE / "assets" / "example_figure.png")
            with patch("scripts.semantic_template_renderer.fetch_logo") as fetch:
                result = render_deck(TEMPLATE, write_plan(work, plan), work / "manual" / "svg_output")
                fetch.assert_not_called()
            root = ET.parse(work / "manual" / "svg_output" / result["assignments"][0]["svg"]).getroot()
            self.assertTrue(any(node.get("data-slot") == "INSTITUTION_LOGO" for node in root.iter()))

    def test_blue_band_ending_is_editable_and_respects_optional_fields(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        plan = json.loads((TEMPLATE / "examples" / "ending_blue_band.json").read_text(encoding="utf-8"))
        template = load_template(TEMPLATE)
        self.assertEqual(resolve_layout(template, plan["slides"][0])["layout_id"], "ending_blue_band")
        self.assertEqual(resolve_layout(template, example_plan()["slides"][-1])["layout_id"], "ending")
        self.assertNotIn("ADVISOR", {s["slot_id"] for s in template.layouts["ending_blue_band"]["slots"]})
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = work / "plain"
            result = render_deck(TEMPLATE, write_plan(work, plan), output)
            svg = output / result["assignments"][0]["svg"]
            root = ET.parse(svg).getroot()
            self.assertTrue(any(node.get("id") == "ending-neutral-mark" for node in root.iter()))
            self.assertFalse(any(node.get("id") == "advisor-icon" for node in root.iter()))
            self.assertFalse(any(node.get("data-slot") in {"INSTITUTION_LOGO", "PAGE_NUM", "SOURCE"}
                                 for node in root.iter()))
            xml, _, _, _ = convert_svg_to_slide_shapes(svg)
            slide = ET.fromstring(xml)
            shapes = slide.findall("p:cSld/p:spTree/p:sp", ns)
            texts = ["".join(shape.itertext()) for shape in shapes]
            self.assertTrue(any("敬请各位老师批评指正" in text for text in texts))
            self.assertTrue(any("汇报人：待填写" in text for text in texts))

            payload = plan["slides"][0]["slot_payload"]
            payload["INSTITUTION_LOGO"] = str(TEMPLATE / "assets" / "example_figure.png")
            del payload["DATE"]
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "with_logo")
            svg = work / "with_logo" / result["assignments"][0]["svg"]
            root = ET.parse(svg).getroot()
            self.assertFalse(any(node.get("id") in {"ending-neutral-mark", "date-icon"}
                                 for node in root.iter()))
            self.assertTrue(any(node.get("data-slot") == "INSTITUTION_LOGO" for node in root.iter()))
            xml, _, _, _ = convert_svg_to_slide_shapes(svg)
            self.assertEqual(len(ET.fromstring(xml).findall(".//p:pic", ns)), 2)

            payload["REF_1"] = "Legacy reference"
            with self.assertRaisesRegex(SemanticTemplateError, "mixes legacy"):
                render_deck(TEMPLATE, write_plan(work, plan), work / "mixed")

    def test_ending_reuses_the_actual_cover_image_and_crop(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        cover = json.loads((TEMPLATE / "examples" / "auto_discipline_cover_toc.json").read_text(encoding="utf-8"))["slides"][0]
        ending = json.loads((TEMPLATE / "examples" / "ending_blue_band.json").read_text(encoding="utf-8"))["slides"][0]
        original = TEMPLATE / "assets" / "evolution_cover_photographic.png"
        cover["slot_payload"]["BAND_IMAGE"] = str(original)
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = {"slides": [cover, ending]}
            output = work / "shared"
            result = render_deck(TEMPLATE, write_plan(work, plan), output)
            paths = [output / row["svg"] for row in result["assignments"]]
            images = [next(node for node in ET.parse(path).getroot().iter()
                           if node.get("data-slot") == "BAND_IMAGE") for path in paths]
            self.assertEqual(images[0].get("href"), images[1].get("href"))
            self.assertTrue(images[1].get("href").endswith(original.name))
            self.assertEqual((images[0].get("width"), images[0].get("height")), ("1280", "330"))
            self.assertEqual((images[1].get("width"), images[1].get("height")), ("1280", "330"))

            slides = [ET.fromstring(convert_svg_to_slide_shapes(path)[0]) for path in paths]
            pics = [slide.find("p:cSld/p:spTree/p:pic", ns) for slide in slides]
            self.assertEqual(pics[0].find(".//a:srcRect", ns).attrib,
                             pics[1].find(".//a:srcRect", ns).attrib)
            self.assertEqual(pics[1].find(".//a:alphaModFix", ns).get("amt"), "70000")
            shapes = list(slides[1].find("p:cSld/p:spTree", ns))
            overlay = next(shape for shape in shapes if shape.find("p:spPr/a:gradFill", ns) is not None)
            title = next(shape for shape in shapes if "敬请各位老师批评指正" in "".join(shape.itertext()))
            self.assertLess(shapes.index(pics[1]), shapes.index(overlay))
            self.assertLess(shapes.index(overlay), shapes.index(title))
            stops = overlay.findall(".//a:gs", ns)
            self.assertEqual([int(stop.find(".//a:alpha", ns).get("val"))
                              if stop.find(".//a:alpha", ns) is not None else 100000
                              for stop in stops], [18000, 62000, 100000, 62000, 18000])

            ending["slot_payload"]["BAND_IMAGE"] = str(TEMPLATE / "assets" / "example_figure.png")
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "override")
            root = ET.parse(work / "override" / result["assignments"][1]["svg"]).getroot()
            self.assertTrue(next(n for n in root.iter() if n.get("data-slot") == "BAND_IMAGE")
                            .get("href").endswith("example_figure.png"))

            ending["slot_payload"]["BAND_IMAGE"] = ""
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "disabled_ending")
            root = ET.parse(work / "disabled_ending" / result["assignments"][1]["svg"]).getroot()
            self.assertFalse(any(n.get("data-slot") == "BAND_IMAGE" for n in root.iter()))

            del ending["slot_payload"]["BAND_IMAGE"]
            cover["slot_payload"]["BAND_IMAGE"] = ""
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "disabled_cover")
            root = ET.parse(work / "disabled_cover" / result["assignments"][1]["svg"]).getroot()
            self.assertFalse(any(n.get("data-slot") == "BAND_IMAGE" for n in root.iter()))

    def test_blue_band_cover_is_explicit_and_exports_editable_text(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        template = load_template(TEMPLATE)
        self.assertEqual(resolve_layout(template, {"role": "cover"})["layout_id"], "cover")
        self.assertEqual(
            resolve_layout(template, {"role": "cover", "layout_id": "cover_blue_band"})["layout_id"],
            "cover_blue_band",
        )
        plan = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))
        ppt_ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = work / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(work, plan), output)
            svg = output / manifest["assignments"][0]["svg"]
            self.assertEqual(slot_text(svg, "TITLE"), ["学术研究与成果汇报"])
            self.assertEqual(slot_text(svg, "REPORTER"), ["汇报人：姓名"])
            self.assertEqual(slot_text(svg, "PAGE_NUM"), [])
            xml, _, _, _ = convert_svg_to_slide_shapes(svg)
            slide = ET.fromstring(xml)
            self.assertEqual(slide.findall(".//p:pic", ppt_ns), [])
            texts = [
                "".join(shape.itertext())
                for shape in slide.findall("p:cSld/p:spTree/p:sp", ppt_ns)
            ]
            self.assertTrue(any("学术研究与成果汇报" in text for text in texts))
            self.assertTrue(any("汇报人：姓名" in text for text in texts))

    def test_blue_band_cover_centers_visible_title_block_in_native_output(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        cases = (("学术论文汇报", False), ("Attention Is All You Need", True),
                 (["生物多样性变化", "与生态系统生产力"], True),
                 ("景观为何而变？\n从《易经》到景观生态学", False))
        for title, with_subtitle in cases:
            with self.subTest(title=title, subtitle=with_subtitle), tempfile.TemporaryDirectory() as tmp:
                plan = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))
                payload = plan["slides"][0]["slot_payload"]
                payload["TITLE"] = title
                if not with_subtitle:
                    payload.pop("SUBTITLE")
                work = Path(tmp)
                output = work / "svg_output"
                manifest = render_deck(TEMPLATE, write_plan(work, plan), output)
                svg = output / manifest["assignments"][0]["svg"]
                root = ET.parse(svg).getroot()
                node = next(n for n in root.iter() if n.get("data-slot") == "TITLE")
                lines = title if isinstance(title, list) else title.splitlines()
                self.assertEqual([n.text for n in node], lines)
                expected_height = 116 if len(lines) == 1 else 180
                xml_band = next(n for n in root.iter() if n.get("id") == "title-band")
                band_y = float(xml_band.get("y")) + float(xml_band.get("height")) / 2
                xml, _, _, _ = convert_svg_to_slide_shapes(svg)
                slide = ET.fromstring(xml)
                boxes = []
                for text in ([lines, [payload["SUBTITLE"]]] if with_subtitle else [lines]):
                    shape = next(n for n in slide.findall(".//p:sp", ns)
                                 if [t.text for t in n.findall(".//a:t", ns)] == text)
                    offset = shape.find("p:spPr/a:xfrm/a:off", ns)
                    extent = shape.find("p:spPr/a:xfrm/a:ext", ns)
                    self.assertAlmostEqual((int(offset.get("x")) + int(extent.get("cx")) / 2) / 9525, 640, places=3)
                    boxes.append((int(offset.get("y")) / 9525, int(extent.get("cy")) / 9525))
                    self.assertEqual(shape.find("p:txBody/a:bodyPr", ns).get("anchor"), "ctr")
                self.assertEqual(boxes[0][1], expected_height)
                self.assertAlmostEqual((boxes[0][0] + sum(boxes[-1])) / 2, band_y, places=3)
                if with_subtitle:
                    self.assertAlmostEqual(boxes[1][0] - sum(boxes[0]), 5, places=3)

    def test_blue_band_cover_image_is_cropped_and_30_percent_transparent(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        plan = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))
        plan["slides"][0]["slot_payload"]["BAND_IMAGE"] = str(TEMPLATE / "assets" / "example_figure.png")
        ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = work / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(work, plan), output)
            svg = output / manifest["assignments"][0]["svg"]
            xml, _, _, _ = convert_svg_to_slide_shapes(svg)
            slide = ET.fromstring(xml)
            pictures = slide.findall("p:cSld/p:spTree/p:pic", ns)
            self.assertEqual(len(pictures), 1)
            picture = pictures[0]
            self.assertEqual(picture.find(".//a:alphaModFix", ns).get("amt"), "70000")
            self.assertIsNotNone(picture.find(".//a:srcRect", ns))
            offset = picture.find("p:spPr/a:xfrm/a:off", ns)
            extent = picture.find("p:spPr/a:xfrm/a:ext", ns)
            self.assertEqual((offset.get("x"), offset.get("y")), ("0", str(120 * 9525)))
            self.assertEqual((extent.get("cx"), extent.get("cy")), (str(1280 * 9525), str(330 * 9525)))
            shapes = list(slide.find("p:cSld/p:spTree", ns))
            title = next(shape for shape in shapes if "学术研究与成果汇报" in "".join(shape.itertext()))
            overlay = next(shape for shape in shapes if shape.find("p:spPr/a:gradFill", ns) is not None)
            self.assertLess(shapes.index(picture), shapes.index(overlay))
            self.assertLess(shapes.index(overlay), shapes.index(title))
            gradient = overlay.find("p:spPr/a:gradFill", ns)
            self.assertEqual(gradient.find("a:lin", ns).get("ang"), "0")
            stops = gradient.findall("a:gsLst/a:gs", ns)
            positions = [int(stop.get("pos")) for stop in stops]
            alphas = [int(alpha.get("val")) if alpha is not None else 100000
                      for stop in stops for alpha in [stop.find(".//a:alpha", ns)]]
            self.assertEqual(positions, [0, 25000, 50000, 75000, 100000])
            self.assertEqual(alphas[0], alphas[-1])
            self.assertEqual(alphas[1], alphas[-2])
            self.assertLess(alphas[0], alphas[1])
            self.assertLess(alphas[1], alphas[2])
            self.assertEqual(alphas[2], 100000)
            overlay_offset = overlay.find("p:spPr/a:xfrm/a:off", ns)
            overlay_extent = overlay.find("p:spPr/a:xfrm/a:ext", ns)
            self.assertEqual((overlay_offset.get("x"), overlay_offset.get("y")), ("0", str(120 * 9525)))
            self.assertEqual((overlay_extent.get("cx"), overlay_extent.get("cy")),
                             (str(1280 * 9525), str(330 * 9525)))

    def test_background_uses_editable_side_diagram_and_lower_takeaway(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes
        ppt_ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
                  "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            manifest = render_deck(TEMPLATE, write_plan(work, example_plan()), work / "out")
            svg = work / "out" / manifest["assignments"][3]["svg"]
            root = ET.parse(svg).getroot()
            slots = {n.get("data-slot"): n for n in root.iter() if n.get("data-slot")}
            left = slots["BACKGROUND_LINE1"]
            steps = [slots[f"DIAGRAM_STEP_{i}"] for i in range(1, 4)]
            self.assertGreater(float(steps[0].get("data-pptx-box-x")),
                               float(left.get("data-pptx-box-x")) + float(left.get("data-pptx-box-w")))
            self.assertEqual(sorted(float(n.get("data-pptx-box-y")) for n in steps),
                             [float(n.get("data-pptx-box-y")) for n in steps])
            self.assertGreater(float(slots["CORE_PROBLEM"].get("data-pptx-box-y")),
                               float(steps[-1].get("data-pptx-box-y")))
            slide, _, _, _ = convert_svg_to_slide_shapes(svg)
            slide = ET.fromstring(slide)
            direct_texts = ["".join(s.itertext()) for s in slide.findall("p:cSld/p:spTree/p:sp", ppt_ns)]
            self.assertTrue(any("已有空白" in t for t in direct_texts))

    def test_toc_distributes_actual_sections_and_uses_native_image_crop(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            for count in (3, 5, 9):
                plan = example_plan()
                plan["discipline_code"] = "08"
                payload = plan["slides"][1]["slot_payload"]
                for index in range(1, 10):
                    if index <= count:
                        payload[f"TOC_ITEM_{index}_TITLE"] = f"研究阶段{index}"
                    else:
                        payload.pop(f"TOC_ITEM_{index}_TITLE", None)
                output = work / f"out_{count}"
                manifest = render_deck(TEMPLATE, write_plan(work, plan), output)
                svg = output / manifest["assignments"][1]["svg"]
                root = ET.parse(svg).getroot()
                titles = [node for node in root.iter() if (node.get("data-slot") or "").startswith("TOC_ITEM_")]
                numbers = [node for node in root.iter() if node.get("data-toc-number-for")]
                self.assertEqual(len(titles), count)
                self.assertEqual(len(numbers), count)
                image = next(node for node in root.iter() if node.get("data-slot") == "TOC_IMAGE")
                image_right = float(image.get("x")) + float(image.get("width"))
                self.assertGreaterEqual(float(numbers[0].get("data-pptx-box-x")) - image_right, 40)
                self.assertGreater(float(titles[0].get("data-pptx-box-x")),
                                   float(numbers[0].get("data-pptx-box-x")))
                self.assertLessEqual(float(titles[0].get("data-pptx-box-x")) +
                                     float(titles[0].get("data-pptx-box-w")), 1280)
                ys = [float(node.get("data-pptx-box-y")) for node in titles]
                self.assertEqual(ys, sorted(ys))
                self.assertEqual((ys[0], ys[-1]), (174, 606))
                slide, _, _, _ = convert_svg_to_slide_shapes(svg)
                crop = ET.fromstring(slide).find(".//a:srcRect", ns)
                self.assertIsNotNone(crop)
                self.assertGreater(int(crop.get("l")), 0)
                self.assertGreater(int(crop.get("r")), 0)

            plan = example_plan()
            del plan["slides"][1]["slot_payload"]["TOC_ITEM_2_TITLE"]
            with self.assertRaisesRegex(SemanticTemplateError, "must start at 1 and be consecutive"):
                render_deck(TEMPLATE, write_plan(work, plan), work / "invalid")

    def test_topic_image_is_shared_and_cropped_for_cover_and_toc(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        cover = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))["slides"][0]
        cover["slot_payload"]["TITLE"] = "Attention Is All You Need"
        toc = example_plan()["slides"][1]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = work / "svg_output"
            result = render_deck(TEMPLATE, write_plan(work, {"slides": [cover, toc]}), output)
            self.assertEqual(result["visual_selection"]["discipline_code"], "08")
            self.assertEqual(result["visual_selection"]["method"], "topic_keywords")
            paths = [output / assignment["svg"] for assignment in result["assignments"]]
            pictures = []
            for path, slot_id in zip(paths, ("BAND_IMAGE", "TOC_IMAGE")):
                svg = ET.parse(path).getroot()
                image = next(node for node in svg.iter() if node.get("data-slot") == slot_id)
                pictures.append(image.get("href"))
            self.assertEqual(pictures[0], pictures[1])
            self.assertTrue((output / pictures[0]).name.endswith("08_工学.png"))

            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            cover_xml, _, _, _ = convert_svg_to_slide_shapes(paths[0])
            toc_xml, _, _, _ = convert_svg_to_slide_shapes(paths[1])
            cover_crop = ET.fromstring(cover_xml).find(".//a:srcRect", ns)
            toc_crop = ET.fromstring(toc_xml).find(".//a:srcRect", ns)
            self.assertGreater(int(cover_crop.get("t")), 0)
            self.assertGreater(int(toc_crop.get("l")), 0)
            self.assertGreater(int(toc_crop.get("r")), 0)

    def test_compatible_unspecified_cover_uses_image_enabled_layout(self):
        cover = {"role": "cover", "slot_payload": {"TITLE": "水稻育种研究", "REPORTER": "汇报人：姓名"}}
        toc = example_plan()["slides"][1]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = {"slides": [cover, toc]}
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "automatic")
            self.assertEqual(result["assignments"][0]["layout_id"], "cover_blue_band")
            self.assertIn("BAND_IMAGE", result["assignments"][0]["rendered_slots"])
            self.assertIn("TOC_IMAGE", result["assignments"][1]["rendered_slots"])

            cover["layout_id"] = "cover"
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "explicit")
            self.assertEqual(result["assignments"][0]["layout_id"], "cover")

            del cover["layout_id"]
            cover["slot_payload"]["AUTHORS"] = "研究作者"
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "legacy")
            self.assertEqual(result["assignments"][0]["layout_id"], "cover")
            self.assertIn("AUTHORS", result["assignments"][0]["rendered_slots"])

    def test_explicit_discipline_and_manual_cover_image_take_priority(self):
        cover = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))["slides"][0]
        cover["slot_payload"]["TITLE"] = "水稻育种研究"
        toc = example_plan()["slides"][1]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = {"discipline_code": "07", "slides": [cover, toc]}
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "first")
            self.assertEqual(result["visual_selection"]["discipline_code"], "07")
            self.assertEqual(result["visual_selection"]["method"], "explicit_category")
            self.assertEqual(result["visual_selection"]["image_source"], "discipline_catalogue")

            cover["slot_payload"]["BAND_IMAGE"] = str(TEMPLATE / "assets" / "evolution_cover_original.png")
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "second")
            self.assertEqual(result["visual_selection"]["image_source"], "provided_cover")
            toc_svg = ET.parse(work / "second" / result["assignments"][1]["svg"]).getroot()
            image = next(node for node in toc_svg.iter() if node.get("data-slot") == "TOC_IMAGE")
            self.assertTrue(image.get("href").endswith("evolution_cover_original.png"))

    def test_unknown_topic_does_not_guess_and_explicit_toc_override_is_respected(self):
        cover = json.loads((TEMPLATE / "examples" / "blue_band_cover.json").read_text(encoding="utf-8"))["slides"][0]
        toc = example_plan()["slides"][1]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = {"slides": [cover, toc]}
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "first")
            self.assertEqual(result["visual_selection"]["status"], "needs_review")
            toc_svg = ET.parse(work / "first" / result["assignments"][1]["svg"]).getroot()
            self.assertFalse(any(node.get("data-slot") == "TOC_IMAGE" for node in toc_svg.iter()))
            self.assertTrue(any(node.get("id") == "toc-neutral-network" for node in toc_svg.iter()))

            plan["discipline_code"] = "09"
            toc["slot_payload"]["TOC_IMAGE"] = str(TEMPLATE / "assets" / "evolution_cover_original.png")
            result = render_deck(TEMPLATE, write_plan(work, plan), work / "second")
            toc_svg = ET.parse(work / "second" / result["assignments"][1]["svg"]).getroot()
            image = next(node for node in toc_svg.iter() if node.get("data-slot") == "TOC_IMAGE")
            self.assertTrue(image.get("href").endswith("evolution_cover_original.png"))

    def test_discipline_matches_and_specific_evolution_asset(self):
        from scripts.academic_paper_visuals import select_discipline_image
        brief_match = select_discipline_image(TEMPLATE, {
            "academic_brief": {"discipline_code": "09", "theme_palette": "technology_blue"}
        }, [])
        self.assertEqual(brief_match["discipline_code"], "09")
        self.assertEqual(brief_match["method"], "explicit_category")

        topics = ["认识论与哲学", "国际贸易与经济学", "法学与宪法", "心理学与教育教学",
                  "唐诗文学研究", "先秦考古研究", "生态系统与生物多样性", "深度学习与自注意力",
                  "水稻育种研究", "临床医学与疾病治疗", "军事战略与军队改革", "公共管理与组织管理",
                  "美术与绘画", "纳米科学与工程"]
        for index, topic in enumerate(topics, start=1):
            with self.subTest(topic=topic):
                slide = {"role": "cover", "slot_payload": {"TITLE": topic}}
                selected = select_discipline_image(TEMPLATE, {}, [slide])
                self.assertEqual(selected["discipline_code"], f"{index:02d}")
                explicit = select_discipline_image(TEMPLATE, {"discipline_code": f"{index:02d}"}, [])
                self.assertEqual(explicit["discipline_code"], f"{index:02d}")
        evolution = select_discipline_image(
            TEMPLATE, {}, [{"role": "cover", "slot_payload": {"TITLE": "生命演化与物种多样性"}}]
        )
        self.assertTrue(evolution["path"].endswith("evolution_cover_photographic.png"))
        evolution_theory = select_discipline_image(TEMPLATE, {"topic": "进化论"}, [])
        self.assertEqual(evolution_theory["discipline_code"], "07")
        self.assertTrue(evolution_theory["path"].endswith("evolution_cover_photographic.png"))

        inferred_from_body = select_discipline_image(TEMPLATE, {}, [
            {"role": "cover", "slot_payload": {"TITLE": "研究报告"}},
            {"role": "content", "slot_payload": {"PAGE_TITLE": "生态系统与生物多样性"}},
        ])
        self.assertEqual(inferred_from_body["discipline_code"], "07")
        self.assertEqual(inferred_from_body["method"], "content_keywords")
        unknown_explicit = select_discipline_image(
            TEMPLATE, {"discipline": "未知方向", "topic": "生态系统"}, []
        )
        self.assertEqual(unknown_explicit["status"], "needs_review")
        ambiguous = select_discipline_image(TEMPLATE, {"topic": "哲学与法学"}, [])
        self.assertEqual(ambiguous["status"], "needs_review")
        self.assertEqual(set(ambiguous["candidates"]), {"01", "03"})

    def test_export_uses_default_background_without_full_slide_shape_or_image(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(root, example_plan()), output)
            for row in manifest["assignments"]:
                svg_path = output / row["svg"]
                xml, _, _, _ = convert_svg_to_slide_shapes(svg_path)
                slide = ET.fromstring(xml)
                self.assertIsNone(slide.find("p:cSld/p:bg", ns), svg_path.name)
                for shape in slide.findall(".//p:sp", ns) + slide.findall(".//p:pic", ns):
                    xfrm = shape.find("p:spPr/a:xfrm", ns)
                    if xfrm is None:
                        continue
                    off, ext = xfrm.find("a:off", ns), xfrm.find("a:ext", ns)
                    if off is not None and ext is not None:
                        self.assertFalse(off.get("x") == "0" and off.get("y") == "0" and
                                         ext.get("cx") == "12192000" and ext.get("cy") == "6858000",
                                         svg_path.name)

    def test_title_markers_center_on_title_text_frames(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        content_files = {row["svg"] for row in layouts if row.get("role") == "content"}
        for path in sorted(TEMPLATE.glob("*.svg")):
            root = ET.parse(path).getroot()
            title = next((node for node in root.iter() if node.get("data-slot") in {"PAGE_TITLE", "CHAPTER_TITLE"}), None)
            if title is None:
                continue
            if path.name in content_files or path.name == "02_toc.svg":
                self.assertFalse(any(node.get("id") == "tab" for node in root.iter()), path.name)
                continue
            marker = next(node for node in root.iter() if node.get("id") == "tab")
            marker_center = float(marker.get("y")) + float(marker.get("height")) / 2
            text_center = float(title.get("data-pptx-box-y")) + float(title.get("data-pptx-box-h")) / 2
            self.assertAlmostEqual(marker_center, text_center, places=4, msg=path.name)

    def test_content_hint_has_clearance_below_header(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        for layout in layouts:
            if layout.get("role") != "content":
                continue
            root = ET.parse(TEMPLATE / layout["svg"]).getroot()
            header = next(node for node in root if node.get("id") == "header-base")
            hints = [node for node in root.iter() if node.get("data-slot") in {"KEY_MESSAGE", "TAKEAWAY"}]
            self.assertEqual(len(hints), 1, layout["layout_id"])
            header_bottom = float(header.get("y")) + float(header.get("height"))
            self.assertGreaterEqual(float(hints[0].get("data-pptx-box-y")) - header_bottom, 24)

    def test_footer_contains_only_source_and_page_number(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        for layout in layouts:
            if layout.get("role") in {"cover", "ending"}:
                continue
            root = ET.parse(TEMPLATE / layout["svg"]).getroot()
            if layout.get("role") == "toc":
                self.assertFalse(any(node.get("data-slot") in {"SOURCE", "PAGE_NUM"} for node in root.iter()))
                continue
            footer = next(node for node in root if node.get("id") == "meta")
            self.assertEqual([node.get("data-slot") for node in footer], ["SOURCE", "PAGE_NUM"], layout["layout_id"])
            self.assertNotIn("FOOTER_SECTION", {slot["slot_id"] for slot in layout["slots"]})

    def test_content_layouts_do_not_use_repeated_pastel_cards(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        card_fills = {"#EEF5F9", "#EDF7F4", "#FAF5EC", "#F2F1F8",
                      "#F2F8F6", "#F4F7FA", "#F5F8FA", "#E4F3EF"}
        svg = "{http://www.w3.org/2000/svg}"
        for layout in layouts:
            if layout.get("role") != "content":
                continue
            root = ET.parse(TEMPLATE / layout["svg"]).getroot()
            for node in root.iter(svg + "rect"):
                if node.get("id") in {"header-base", "header-chapter"}:
                    continue
                if node.get("fill", "").upper() not in card_fills:
                    continue
                with self.subTest(layout=layout["layout_id"], rectangle=node.attrib):
                    self.assertFalse(float(node.get("width", 0)) >= 180 and
                                     float(node.get("height", 0)) >= 55)

    def test_page_badge_is_flush_and_number_is_centered_in_all_numbered_layouts(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        for layout in layouts:
            if not any(slot.get("slot_id") == "PAGE_NUM" for slot in layout["slots"]):
                continue
            root = ET.parse(TEMPLATE / layout["svg"]).getroot()
            badge = next(node for node in root.iter() if node.get("id") == "page-number-badge")
            number = next(node for node in root.iter() if node.get("data-slot") == "PAGE_NUM")
            self.assertEqual(badge.get("d"), "M 1244 672 H 1280 V 720 H 1232 V 684 Q 1232 672 1244 672 Z")
            self.assertEqual(badge.get("fill"), "#D8E1E9")
            self.assertEqual((number.get("data-pptx-box-x"), number.get("data-pptx-box-y"),
                              number.get("data-pptx-box-w"), number.get("data-pptx-box-h")),
                             ("1232", "672", "48", "48"))
            self.assertEqual((number.get("font-family"), number.get("font-weight")), ("Cambria", "700"))
            self.assertEqual((number.get("text-anchor"), number.get("data-pptx-valign")), ("middle", "middle"))
            self.assertFalse(any(n.tag.rsplit("}", 1)[-1] == "line" and n.get("y1") == "672"
                                 and n.get("y2") == "672" for n in root.iter()))

    def test_page_numbers_1_and_11_share_the_same_native_centered_16pt_frame(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        chapter = example_plan()["slides"][2]
        plan = {"slides": [copy.deepcopy(chapter) for _ in range(11)]}
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(work, plan), out)
            positions = []
            for index, expected in ((0, "1"), (10, "11")):
                svg = out / manifest["assignments"][index]["svg"]
                self.assertEqual(slot_text(svg, "PAGE_NUM"), [expected])
                xml, _, _, _ = convert_svg_to_slide_shapes(svg)
                root = ET.fromstring(xml)
                number = next(shape for shape in root.findall(".//p:sp", ns)
                              if "".join(n.text or "" for n in shape.findall(".//a:t", ns)) == expected)
                offset = number.find("p:spPr/a:xfrm/a:off", ns)
                extent = number.find("p:spPr/a:xfrm/a:ext", ns)
                body = number.find("p:txBody/a:bodyPr", ns)
                paragraph = number.find("p:txBody/a:p/a:pPr", ns)
                run = number.find(".//a:rPr", ns)
                positions.append((offset.get("x"), offset.get("y"), extent.get("cx"), extent.get("cy")))
                self.assertEqual(body.get("anchor"), "ctr")
                self.assertEqual(paragraph.get("algn"), "ctr")
                self.assertEqual((run.get("sz"), run.get("b")), ("1600", "1"))
                self.assertEqual(run.find("a:latin", ns).get("typeface"), "Cambria")
            self.assertEqual(positions[0], positions[1])
            self.assertEqual(tuple(map(int, positions[0])), tuple(n * 9525 for n in (1232, 672, 48, 48)))

    def test_first_citation_only_preserves_distinct_sources_and_parent_figures(self):
        base = example_plan()["slides"][3]
        refs = [(None, None), ("paper:a", "Vaswani et al., 2017, §3.1"),
                ("fig:a", "Vaswani et al., 2017, Fig. 1"),
                ("paper:b", "Vaswani et al., 2017, Table 2"),
                ("fig:b", "Vaswani et al., 2017, Fig. 3"),
                ("paper:a", "Vaswani et al., 2017, §3.2")]
        slides = []
        for source_id, source in refs:
            slide = copy.deepcopy(base)
            if source:
                slide["slot_payload"]["SOURCE"] = source
                slide["evidence_sources"] = [{"source_id": source_id}]
            slides.append(slide)
        plan = {"source_map": [{"id": "paper:a"}, {"id": "fig:a", "parent_source": "paper:a"},
                               {"id": "paper:b"}, {"id": "fig:b", "parent_source": "paper:b"}],
                "slides": slides}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(work, plan), out)
            values = [slot_text(out / row["svg"], "SOURCE") for row in manifest["assignments"]]
            self.assertEqual(values, [[], [refs[1][1]], [], [refs[3][1]], [], []])
            self.assertEqual(manifest["assignments"][2]["footer_source"]["status"], "repeat_suppressed")
            self.assertEqual(manifest["assignments"][2]["footer_source"]["original"], refs[2][1])

            # Without structured evidence, ordinary figure/section locators of
            # the same author-year citation still resolve to one visible source.
            first, second = copy.deepcopy(base), copy.deepcopy(base)
            first["slot_payload"]["SOURCE"] = "Vaswani et al., 2017, §3.1"
            second["slot_payload"]["SOURCE"] = "Vaswani et al., 2017, Fig. 2"
            result = render_deck(TEMPLATE, write_plan(work, {"slides": [first, second]}), out)
            self.assertEqual(slot_text(out / result["assignments"][0]["svg"], "SOURCE"),
                             [first["slot_payload"]["SOURCE"]])
            self.assertEqual(slot_text(out / result["assignments"][1]["svg"], "SOURCE"), [])

    def test_content_chapter_label_is_centered_in_header_rectangle(self):
        layouts = json.loads((TEMPLATE / "layouts.json").read_text(encoding="utf-8"))["layouts"]
        for layout in layouts:
            if layout.get("role") != "content":
                continue
            root = ET.parse(TEMPLATE / layout["svg"]).getroot()
            rectangle = next(node for node in root if node.get("id") == "header-chapter")
            label = next(node for node in root if node.get("data-slot") == "CHAPTER_LABEL")
            page_title = next(node for node in root.iter() if node.get("data-slot") == "PAGE_TITLE")
            self.assertEqual(rectangle.get("fill"), "#08264D")
            self.assertEqual(rectangle.get("fill-opacity"), "0.75")
            self.assertEqual(label.get("fill"), "#FFFFFF")
            for axis, size in (("x", "width"), ("y", "height")):
                rect_center = float(rectangle.get(axis)) + float(rectangle.get(size)) / 2
                box_center = float(label.get(f"data-pptx-box-{axis}")) + float(label.get(f"data-pptx-box-{'w' if axis == 'x' else 'h'}")) / 2
                self.assertAlmostEqual(rect_center, box_center, msg=layout["layout_id"])
            self.assertEqual(label.get("text-anchor"), "middle")
            self.assertEqual(label.get("data-pptx-valign"), "middle")
            for attr in ("y", "font-family", "font-size", "font-weight", "data-pptx-box-y",
                         "data-pptx-box-h", "data-pptx-valign"):
                self.assertEqual(label.get(attr), page_title.get(attr), f"{layout['layout_id']}: {attr}")

    def test_exported_content_titles_share_native_powerpoint_vertical_center(self):
        from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes

        content = next(slide for slide in example_plan()["slides"]
                       if slide.get("content_shape") == "figure")
        content["slot_payload"]["FIGURE"] = str(TEMPLATE / "assets/example_figure.png")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = work / "svg_output"
            manifest = render_deck(TEMPLATE, write_plan(work, {"slides": [content]}), output)
            xml, _, _, _ = convert_svg_to_slide_shapes(output / manifest["assignments"][0]["svg"])
        slide = ET.fromstring(xml)
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        shapes = {}
        for shape in slide.findall(".//p:sp", ns):
            text = "".join(node.text or "" for node in shape.findall(".//a:t", ns))
            if text in (content["slot_payload"]["CHAPTER_LABEL"], content["slot_payload"]["PAGE_TITLE"]):
                shapes[text] = shape
        self.assertEqual(len(shapes), 2)
        vertical = []
        for shape in shapes.values():
            offset = shape.find("p:spPr/a:xfrm/a:off", ns)
            extent = shape.find("p:spPr/a:xfrm/a:ext", ns)
            body = shape.find("p:txBody/a:bodyPr", ns)
            run = shape.find(".//a:rPr", ns)
            vertical.append((int(offset.get("y")), int(extent.get("cy"))))
            self.assertEqual(body.get("anchor"), "ctr")
            self.assertEqual(run.get("sz"), "2800")
            self.assertEqual(run.find("a:ea", ns).get("typeface"), "Microsoft YaHei")
        self.assertEqual(vertical[0], vertical[1])
        self.assertEqual(2 * vertical[0][0] + vertical[0][1], 92 * 9525)

    def test_figure_takeaway_declares_native_bullet_and_preview_only_marker(self):
        root = ET.parse(TEMPLATE / "06_result_figure.svg").getroot()
        text = next(node for node in root.iter() if node.get("data-slot") == "TAKEAWAY")
        self.assertEqual(text.get("data-pptx-bullet"), "square")
        self.assertFalse((text.text or "").startswith("■"))
        preview = [node for node in root.iter() if node.get("data-pptx-preview-only") == "true"]
        self.assertEqual(len(preview), 1)

    def test_explicit_template_routes_content_by_shape(self):
        template = load_template(TEMPLATE)
        for shape, expected in {
            "background": "background",
            "method": "method_pipeline",
            "figure": "result_figure",
            "table": "result_table",
            "conclusion": "conclusion",
            "outlook": "outlook",
        }.items():
            with self.subTest(shape=shape):
                self.assertEqual(resolve_layout(template, {"role": "content", "content_shape": shape})["layout_id"], expected)

    def test_sample_binds_figures_and_uses_physical_page_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = render_deck(TEMPLATE, write_plan(root, example_plan()), root / "svg_output")
            outputs = [root / "svg_output" / row["svg"] for row in manifest["assignments"]]
            self.assertEqual(len(outputs), 10)
            self.assertEqual(slot_text(outputs[0], "PAGE_NUM"), [])
            self.assertEqual(slot_text(outputs[1], "PAGE_NUM"), [])
            self.assertEqual(slot_text(outputs[1], "SOURCE"), [])
            self.assertEqual(slot_text(outputs[-1], "PAGE_NUM"), [])
            for index, path in enumerate(outputs[2:-1], start=3):
                self.assertEqual(slot_text(path, "PAGE_NUM"), [str(index)])
            for path in outputs:
                self.assertNotIn("{{", path.read_text(encoding="utf-8"))
            figure = ET.parse(outputs[5]).getroot()
            image = next(node for node in figure.iter() if node.get("data-slot") == "FIGURE")
            self.assertTrue((root / "svg_output" / image.get("href")).is_file())
            self.assertEqual(slot_text(outputs[0], "TITLE"), ["学术论文汇报示例方法与证据展示"])

    def test_counter_cannot_disagree_with_deck_position(self):
        plan = example_plan()
        plan["slides"][2]["slot_payload"]["PAGE_NUM"] = "99"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(SemanticTemplateError, "PAGE_NUM is template-owned"):
                render_deck(TEMPLATE, write_plan(root, plan), root / "svg_output")

    def test_content_chapter_label_is_at_most_five_characters(self):
        plan = example_plan()
        plan["slides"][3]["slot_payload"]["CHAPTER_LABEL"] = "ABCDEF"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(SlotCapacityError, "5-character limit"):
                render_deck(TEMPLATE, write_plan(root, plan), root / "svg_output")

    def test_long_cover_title_requires_explicit_lines(self):
        plan = example_plan()
        plan["slides"][0]["slot_payload"]["TITLE"] = "字" * 23
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(SlotCapacityError, "explicit line breaks"):
                render_deck(TEMPLATE, write_plan(root, plan), root / "svg_output")

    def test_templates_without_automatic_numbering_keep_caller_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template"
            shutil.copytree(TEMPLATE, template)
            layouts_path = template / "layouts.json"
            layouts = json.loads(layouts_path.read_text(encoding="utf-8"))
            chapter = next(row for row in layouts["layouts"] if row["layout_id"] == "chapter")
            counter = next(slot for slot in chapter["slots"] if slot["slot_id"] == "PAGE_NUM")
            del counter["value_policy"]
            layouts_path.write_text(json.dumps(layouts), encoding="utf-8")
            slide = example_plan()["slides"][2]
            slide["slot_payload"]["PAGE_NUM"] = "31"
            render_deck(template, write_plan(root, {"slides": [slide]}), root / "svg_output")
            self.assertEqual(slot_text(root / "svg_output" / "01_chapter.svg", "PAGE_NUM"), ["31"])

    def test_bundle_includes_official_native_default_without_reference_evidence(self):
        from scripts.build_plugin_bundle import _copy_templates
        from scripts.template_package import validate_package

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "templates"
            official = _copy_templates(target)
            package = target / "layouts" / "academic_general"
            self.assertIn("academic_general", official)
            self.assertEqual(validate_package(package)["status"], "pass")
            self.assertTrue((package / "LICENSE").is_file())
            self.assertTrue((package / "ATTRIBUTION.md").is_file())
            self.assertTrue((package / "assets" / "example_figure.png").is_file())
            self.assertTrue((package / "cover_banners" / "manifest.json").is_file())
            self.assertFalse((package / "assets" / "toc_user_reference.png").exists())
            self.assertFalse((package / "source").exists())


if __name__ == "__main__":
    unittest.main()
