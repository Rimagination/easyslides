import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts.clarification_gate import (
    answer_clarification_request,
    build_clarification_request,
    next_clarification_question,
    validate_clarification_request,
)
import scripts.clarification_gate as clarification_gate
from scripts.semantic_template_renderer import SemanticTemplateError, render_deck
from scripts.template_palette import palette_color_replacements, read_palette_catalog


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/layouts/academic_general"


@pytest.mark.parametrize("academic", [False, True])
def test_selected_template_asks_theme_after_route_and_skips_a_known_choice(academic):
    request = build_clarification_request("paper_deck", known={
        "template_path": str(TEMPLATE), "production_scheme": "direct_editable"
    }, academic=academic)
    question = next_clarification_question(request)
    assert question["question_id"] == "theme_palette"
    preview = Path(question["preview"]["path"])
    assert preview == TEMPLATE / "assets/theme_palette_preview.png"
    assert preview.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    selected = answer_clarification_request(request, {"theme_palette": "academic_purple"})
    assert selected["decisions"]["theme_palette"] == "academic_purple"
    after_selection = next_clarification_question(selected)
    assert after_selection["question_id"] != "theme_palette"
    assert "preview" not in after_selection
    known = build_clarification_request("paper_deck", known={
        "template_path": str(TEMPLATE), "theme_palette": "academic_green"
    }, academic=academic)
    assert "theme_palette" not in known["pending_question_ids"]
    assert validate_clarification_request(known)["status"] == "pass"


def test_missing_saved_preview_does_not_trigger_a_render_or_block_the_question(tmp_path, monkeypatch):
    monkeypatch.setattr(clarification_gate, "ACADEMIC_PAPER_THEME_PREVIEW", tmp_path / "missing.png")
    request = build_clarification_request("paper_deck", known={"template_path": str(TEMPLATE), "production_scheme": "direct_editable"})
    question = next_clarification_question(request)
    assert question["question_id"] == "theme_palette"
    assert "preview" not in question
    assert not (tmp_path / "missing.png").exists()


def test_theme_question_is_scoped_to_the_selected_template_and_accepts_custom_hex():
    other = build_clarification_request("paper_deck", known={"template_id": "academic_classic"})
    assert "theme_palette" not in other["pending_question_ids"]
    existing = build_clarification_request("native_enhance", known={"template_path": str(TEMPLATE)})
    assert "theme_palette" not in existing["pending_question_ids"]
    request = build_clarification_request("paper_deck", known={"template_path": str(TEMPLATE)})
    answer = answer_clarification_request(request, {"theme_palette": "#E4BE30"})
    assert answer["decisions"]["theme_palette"] == "#E4BE30"
    assert validate_clarification_request(answer)["status"] == "pass"
    confirmed = build_clarification_request("paper_deck", known={
        "template_path": str(TEMPLATE), "theme_palette": "academic_blue",
        "production_scheme": "direct_editable", "presentation_mode": "standard",
        "audience": "mixed", "evidence_scope": "selected", "story_policy": "paper_order",
        "presentation_identity": "已检查材料；学校、汇报人和日期由用户明确省略；学科理学。",
        "theme_image_source": "template_assets"
    })
    assert confirmed["status"] == "confirmed"
    confirmed["decisions"].pop("theme_palette")
    assert validate_clarification_request(confirmed)["status"] == "fail"


def _plan(theme=None):
    plan = {"slides": [
        {"role": "cover", "layout_id": "cover_blue_band", "slot_payload": {
            "TITLE": "研究汇报", "REPORTER": "汇报人", "BAND_IMAGE": ""
        }},
        {"role": "toc", "slot_payload": {"PAGE_TITLE": "目录", "TOC_ITEM_1_TITLE": "研究方法", "TOC_IMAGE": ""}},
        {"role": "content", "layout_id": "result_figure", "slot_payload": {
            "CHAPTER_LABEL": "研究方法", "PAGE_TITLE": "颜色代码 #102F4A",
            "TAKEAWAY": "根据材料解释研究问题。", "FIGURE": str(TEMPLATE / "assets/example_figure.png"),
            "SOURCE": "资料来源"
        }},
        {"role": "ending", "layout_id": "ending_blue_band", "slot_payload": {
            "THANK_YOU": "感谢垂听", "INSTITUTION_LOGO": "", "BAND_IMAGE": ""
        }},
    ]}
    if theme:
        plan["theme_palette"] = theme
    return plan


def _node(svg_path, node_id):
    return next(n for n in ET.parse(svg_path).getroot().iter() if n.get("id") == node_id)


def test_custom_theme_image_requires_the_actual_asset_and_reuses_it(tmp_path):
    plan = _plan('academic_green')
    plan['academic_brief'] = {'theme_image_source': 'generate_new'}
    for index, key in ((0, 'BAND_IMAGE'), (1, 'TOC_IMAGE'), (3, 'BAND_IMAGE')):
        plan['slides'][index]['slot_payload'].pop(key)
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(SemanticTemplateError, match='requires its theme image'):
        render_deck(TEMPLATE, path, tmp_path / 'pending')
    plan['academic_brief']['theme_image_path'] = str(TEMPLATE / 'assets/example_figure.png')
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    result = render_deck(TEMPLATE, path, tmp_path / 'ready')
    assert result['visual_selection']['image_source'] == 'generate_new'
    paths = []
    for row, slot in zip(result['assignments'], ['BAND_IMAGE', 'TOC_IMAGE', 'CHAPTER_IMAGE', 'BAND_IMAGE']):
        root = ET.parse(tmp_path / 'ready' / row['svg']).getroot()
        node = next(n for n in root.iter() if n.get('data-slot') == slot)
        paths.append(next(n.get('href') for n in node.iter() if n.get('href')))
    assert len(set(paths)) == 1
    assert not any(node.get('id') == 'title-band-fallback-bars'
                   for node in ET.parse(tmp_path / 'ready' / '01_cover_blue_band.svg').getroot().iter())
    toc = ET.parse(tmp_path / 'ready' / '02_toc.svg').getroot()
    assert not any(node.get('id') == 'toc-neutral-network' for node in toc.iter())
    assert any(node.get('fill') == 'url(#toc-image-fade)' for node in toc)


@pytest.mark.parametrize("theme", ["academic_blue", "academic_purple", "academic_green", "technology_blue", "#E4BE30"])
def test_theme_is_applied_to_all_layouts_without_touching_user_text_or_picture(tmp_path, theme):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(_plan(theme), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "svg_output"
    manifest = render_deck(TEMPLATE, path, out)
    catalog = read_palette_catalog(TEMPLATE)
    replacements = palette_color_replacements(catalog, theme)
    assert manifest["theme_palette"]["id"] == theme
    assert _node(out / "01_cover_blue_band.svg", "title-band").get("fill") == replacements["#063C8D"]
    assert len(_node(out / "01_cover_blue_band.svg", "title-band-fallback-bars")) == 6
    assert _node(out / "02_toc.svg", "toc-neutral-network") is not None
    assert _node(out / "03_result_figure.svg", "header-chapter").get("fill") == replacements["#08264D"]
    assert _node(out / "03_result_figure.svg", "header-base").get("fill") == replacements["#EEF5F9"]
    assert _node(out / "03_result_figure.svg", "page-number-badge").get("fill") == replacements["#D8E1E9"]
    number = next(n for n in ET.parse(out / "03_result_figure.svg").getroot().iter()
                  if n.get("data-slot") == "PAGE_NUM")
    assert number.get("fill") == replacements["#2F759B"]
    assert _node(out / "04_ending_blue_band.svg", "ending-band").get("fill") == replacements["#063C8D"]
    if theme.startswith("#"):
        color = replacements["#102F4A"]
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        assert 1.05 / (luminance + 0.05) >= 4.5
    assert "颜色代码 #102F4A" in (out / "03_result_figure.svg").read_text(encoding="utf-8")
    figure = next(n for n in ET.parse(out / "03_result_figure.svg").getroot().iter() if n.get("data-slot") == "FIGURE")
    assert (out / figure.get("href")).read_bytes() == (TEMPLATE / "assets/example_figure.png").read_bytes()
    gradient = _node(out / "01_cover_blue_band.svg", "title-band-gradient")
    assert [n.get("stop-opacity") for n in gradient] == ["0.18", "0.62", "1", "0.62", "0.18"]
    assert all(n.get("stop-color") == replacements["#08264D"] for n in gradient)


def test_legacy_plan_keeps_original_theme_and_invalid_or_conflicting_colors_fail(tmp_path):
    path = tmp_path / "plan.json"
    out = tmp_path / "svg_output"
    path.write_text(json.dumps(_plan(), ensure_ascii=False), encoding="utf-8")
    manifest = render_deck(TEMPLATE, path, out)
    assert "theme_palette" not in manifest
    assert _node(out / "03_result_figure.svg", "header-chapter").get("fill") == "#08264D"
    path.write_text(json.dumps(_plan("not-a-theme"), ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticTemplateError):
        render_deck(TEMPLATE, path, out)
    plan = _plan("academic_blue")
    plan["academic_brief"] = {"theme_palette": "academic_green"}
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticTemplateError, match="conflicts"):
        render_deck(TEMPLATE, path, out)


def test_preview_pairings_do_not_override_user_discipline_or_cover_image(tmp_path):
    plan = _plan("academic_green")
    plan["discipline_code"] = "08"
    for index, key in ((0, "BAND_IMAGE"), (1, "TOC_IMAGE"), (3, "BAND_IMAGE")):
        plan["slides"][index]["slot_payload"].pop(key)
    path = tmp_path / "plan.json"
    out = tmp_path / "svg_output"

    def render_and_images():
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        manifest = render_deck(TEMPLATE, path, out)
        images = []
        for filename, slot in (("01_cover_blue_band.svg", "BAND_IMAGE"),
                               ("02_toc.svg", "TOC_IMAGE"),
                               ("03_result_figure.svg", "CHAPTER_IMAGE"),
                               ("04_ending_blue_band.svg", "BAND_IMAGE")):
            node = next(n for n in ET.parse(out / filename).getroot().iter()
                        if n.get("data-slot") == slot)
            image = next(n for n in node.iter() if n.tag.rsplit("}", 1)[-1] == "image")
            images.append((out / image.get("href")).read_bytes())
        return manifest, images

    manifest, images = render_and_images()
    engineering = (TEMPLATE / "cover_banners/08_工学.png").read_bytes()
    assert manifest["visual_selection"]["discipline_code"] == "08"
    assert all(image == engineering for image in images)

    user_image = TEMPLATE / "cover_banners/09_农学.png"
    plan["slides"][0]["slot_payload"]["BAND_IMAGE"] = str(user_image)
    manifest, images = render_and_images()
    assert manifest["visual_selection"]["image_source"] == "provided_cover"
    assert all(image == user_image.read_bytes() for image in images)

    plan["slides"][2]["slot_payload"]["CHAPTER_IMAGE"] = str(TEMPLATE / "cover_banners/08_工学.png")
    _, images = render_and_images()
    assert images[2] == engineering
    assert all(images[index] == user_image.read_bytes() for index in (0, 1, 3))

    from scripts.svg_to_pptx.drawingml_converter import convert_svg_to_slide_shapes
    xml, media, _, _ = convert_svg_to_slide_shapes(out / "03_result_figure.svg")
    slide = ET.fromstring(xml)
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
          "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    picture = slide.find(".//p:pic", ns)
    crop = picture.find("p:blipFill/a:srcRect", ns)
    assert int(crop.get("l")) >= 10000 and int(crop.get("r")) >= 10000
    assert any(item == engineering for item in media.values())
    assert slide.find(".//a:solidFill/a:srgbClr/a:alpha[@val='75000']", ns) is not None


def test_content_header_is_solid_when_image_is_explicitly_disabled(tmp_path):
    plan = _plan("academic_green")
    plan["discipline_code"] = "08"
    plan["slides"][2]["slot_payload"]["CHAPTER_IMAGE"] = ""
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "svg_output"
    render_deck(TEMPLATE, path, out)
    root = ET.parse(out / "03_result_figure.svg").getroot()
    assert not any(n.get("data-slot") == "CHAPTER_IMAGE" for n in root.iter())
    header = next(n for n in root.iter() if n.get("id") == "header-chapter")
    assert header.get("fill-opacity") is None
