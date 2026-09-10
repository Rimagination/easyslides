"""Resolve template slot content while preserving surrounding SVG geometry."""
from xml.etree import ElementTree as ET


XLINK_NS = "http://www.w3.org/1999/xlink"


def slot_content_node(node: ET.Element, tag: str) -> ET.Element:
    """Accept direct content, an inline text span, or a single-content wrapper."""
    if tag == "text" and node.tag.rsplit("}", 1)[-1] == "tspan":
        return node
    matches = [child for child in node.iter() if child.tag.rsplit("}", 1)[-1] == tag]
    if len(matches) != 1:
        slot_id = node.get("data-slot") or node.get("data-slot-id") or "<unnamed>"
        raise ValueError(f"{tag} slot {slot_id!r} must contain exactly one {tag}; found {len(matches)}")
    return matches[0]


def set_image_slot_href(node: ET.Element, href: str) -> None:
    """Bind the image inside a slot without replacing its frame or label."""
    image = slot_content_node(node, "image")
    image.set("href", href)
    image.set(f"{{{XLINK_NS}}}href", href)
