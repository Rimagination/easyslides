from xml.etree import ElementTree as ET

from scripts.adaptive_bullets import sync_adaptive_bullets


SVG_NS = "http://www.w3.org/2000/svg"


def _root() -> ET.Element:
    root = ET.Element(f"{{{SVG_NS}}}svg")
    for index in (1, 2):
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}g",
            {
                "data-easyslides-bullet-for": "BODY_TEXT_01",
                "data-easyslides-bullet-index": str(index),
            },
        )
    return root


def test_single_line_removes_second_dot() -> None:
    root = _root()
    report = sync_adaptive_bullets(root, {"BODY_TEXT_01": "只有一行"})
    assert report["removed_count"] == 1
    assert len(list(root)) == 1


def test_two_lines_keep_both_dots() -> None:
    root = _root()
    report = sync_adaptive_bullets(root, {"BODY_TEXT_01": "第一行\n第二行"})
    assert report["removed_count"] == 0
    assert len(list(root)) == 2
