from pathlib import Path
from xml.etree import ElementTree as ET


def test_source_template_projection_replaces_declared_slots_and_center_locks_text(tmp_path: Path):
    from scripts.component_renderer_registry import validate_renderer_id
    from scripts.source_template_renderer import project_source_template_svg

    source = tmp_path / "source.svg"
    output = tmp_path / "projected.svg"
    source.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 400 240">
  <rect x="0" y="0" width="400" height="240" fill="#FFFFFF"/>
  <text data-pptx-textbox="true" data-pptx-box-x="40" data-pptx-box-y="40" data-pptx-box-w="220" data-pptx-box-h="60" x="150" y="70" font-size="24" fill="#111111">Old title</text>
  <image x="280" y="40" width="80" height="80" href="old.png"/>
</svg>""",
        encoding="utf-8",
    )
    slots = [
        {
            "slot_id": "slide_01_title_2",
            "kind": "text",
            "geometry": {"x": 40, "y": 40, "width": 220, "height": 60},
            "capacity": {"max_lines": 2, "max_chars_per_line": 18},
        },
        {
            "slot_id": "slide_01_image_3",
            "kind": "image",
            "geometry": {"x": 280, "y": 40, "width": 80, "height": 80},
        },
    ]

    report = project_source_template_svg(
        source,
        output,
        slots=slots,
        values={"slide_01_title_2": "New evidence title", "slide_01_image_3": "figure.png"},
    )
    root = ET.parse(output).getroot()
    text = next(element for element in root.iter() if element.tag.endswith("text"))
    image = next(element for element in root.iter() if element.tag.endswith("image"))

    assert report["status"] == "pass"
    assert report["replaced_slots"] == ["slide_01_title_2", "slide_01_image_3"]
    assert text.attrib["data-pptx-valign"] == "middle"
    assert text.attrib["data-center-lock"] == "true"
    assert text.attrib["data-slot-id"] == "slide_01_title_2"
    assert text.attrib["x"] == "150.0"
    assert image.attrib["href"] == "figure.png"
    assert validate_renderer_id("source_template_projection", target="svg")["status"] == "pass"


def test_missing_source_slot_fails_closed(tmp_path: Path):
    from scripts.source_template_renderer import project_source_template_svg

    source = tmp_path / "source.svg"
    output = tmp_path / "projected.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    report = project_source_template_svg(
        source,
        output,
        slots=[{"slot_id": "missing", "kind": "text", "geometry": {"x": 1, "y": 1, "width": 10, "height": 10}}],
        values={"missing": "value"},
    )

    assert report["status"] == "fail"
    assert report["issues"][0]["code"] == "SOURCE-SLOT-ELEMENT-NOT-FOUND"


def test_projection_preserves_horizontal_anchor_while_center_locking_vertical_position(tmp_path: Path):
    from scripts.source_template_renderer import project_source_template_svg

    source = tmp_path / "source.svg"
    output = tmp_path / "projected.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text data-pptx-textbox="true" data-pptx-box-x="20" data-pptx-box-y="40" data-pptx-box-w="120" data-pptx-box-h="40" x="20" y="60" font-size="20" text-anchor="start">Old</text></svg>',
        encoding="utf-8",
    )
    report = project_source_template_svg(
        source,
        output,
        slots=[
            {
                "slot_id": "title",
                "kind": "text",
                "geometry": {"x": 20, "y": 40, "width": 120, "height": 40},
                "text_anchor": "start",
            }
        ],
        values={"title": "Aligned"},
    )
    root = ET.parse(output).getroot()
    text = next(element for element in root.iter() if element.tag.endswith("text"))

    assert report["status"] == "pass"
    assert text.attrib["text-anchor"] == "start"
    assert text.attrib["x"] == "20.0"
    assert text.attrib["data-pptx-valign"] == "middle"
