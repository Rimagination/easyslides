"""Fail-closed geometry checks for named SVG text slots.

This is deliberately smaller than the full template geometry gate.  It checks
the contract that matters before a named-slot variant is selected: editable
text boxes must not overlap one another, and one slot id must not silently
occupy several different boxes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SCHEMA_VERSION = "easyslides.named_slot_geometry_report.v1"
MIN_OVERLAP_AREA = 4.0
MIN_OVERLAP_RATIO = 0.03


@dataclass(frozen=True)
class SlotBox:
    slot_id: str
    element_index: int
    text: str
    x: float
    y: float
    width: float
    height: float
    fill: str

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _element_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _slot_box(element: ET.Element, index: int) -> SlotBox | None:
    if _local_name(element.tag) != "text":
        return None
    if str(element.attrib.get("data-pptx-textbox") or "").lower() != "true":
        return None
    slot_id = str(element.attrib.get("data-slot-id") or element.attrib.get("data-slot") or "").strip()
    if not slot_id:
        return None
    values = [_number(element.attrib.get(f"data-pptx-box-{key}")) for key in ("x", "y", "w", "h")]
    if any(value is None for value in values):
        return None
    x, y, width, height = (float(value) for value in values)
    if width <= 0 or height <= 0:
        return None
    return SlotBox(
        slot_id=slot_id,
        element_index=index,
        text=_element_text(element),
        x=x,
        y=y,
        width=width,
        height=height,
        fill=str(element.attrib.get("fill") or ""),
    )


def parse_named_text_slots(svg_path: str | Path) -> list[SlotBox]:
    root = ET.parse(svg_path).getroot()
    return [
        slot
        for index, element in enumerate(root.iter(), start=1)
        if (slot := _slot_box(element, index)) is not None
    ]


def _overlap_area(left: SlotBox, right: SlotBox) -> float:
    width = min(left.right, right.right) - max(left.x, right.x)
    height = min(left.bottom, right.bottom) - max(left.y, right.y)
    if width <= 0 or height <= 0:
        return 0.0
    return width * height


def _box_payload(box: SlotBox) -> dict[str, Any]:
    return {
        "slot_id": box.slot_id,
        "element_index": box.element_index,
        "text_preview": box.text[:120],
        "x": round(box.x, 2),
        "y": round(box.y, 2),
        "width": round(box.width, 2),
        "height": round(box.height, 2),
        "fill": box.fill,
    }


def validate_named_text_slots(
    svg_path: str | Path,
    *,
    allowed_overlaps: set[frozenset[str]] | None = None,
) -> dict[str, Any]:
    """Return a blocking report when named text slots have unsafe geometry."""
    path = Path(svg_path)
    slots = parse_named_text_slots(path)
    issues: list[dict[str, Any]] = []
    by_slot: dict[str, list[SlotBox]] = defaultdict(list)
    for slot in slots:
        by_slot[slot.slot_id].append(slot)

    for slot_id, boxes in sorted(by_slot.items()):
        distinct_boxes = {
            (round(box.x, 3), round(box.y, 3), round(box.width, 3), round(box.height, 3))
            for box in boxes
        }
        if len(distinct_boxes) > 1:
            issues.append(
                {
                    "code": "NAMED-SLOT-DUPLICATE-GEOMETRY",
                    "severity": "blocking",
                    "message": f"named slot {slot_id!r} occupies multiple text boxes; one payload would be duplicated",
                    "slot_id": slot_id,
                    "boxes": [_box_payload(box) for box in boxes],
                }
            )

    allowed_overlaps = allowed_overlaps or set()
    for index, left in enumerate(slots):
        for right in slots[index + 1 :]:
            if left.slot_id == right.slot_id:
                continue
            if frozenset((left.slot_id, right.slot_id)) in allowed_overlaps:
                continue
            area = _overlap_area(left, right)
            if area <= MIN_OVERLAP_AREA:
                continue
            smaller_area = max(min(left.area, right.area), 1.0)
            if area / smaller_area < MIN_OVERLAP_RATIO:
                continue
            issues.append(
                {
                    "code": "NAMED-SLOT-TEXT-OVERLAP",
                    "severity": "blocking",
                    "message": f"named text slots {left.slot_id!r} and {right.slot_id!r} overlap",
                    "overlap_area": round(area, 2),
                    "overlap_ratio_to_smaller": round(area / smaller_area, 3),
                    "left": _box_payload(left),
                    "right": _box_payload(right),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "svg": str(path),
        "slot_count": len(slots),
        "named_slot_count": len(by_slot),
        "issues": issues,
        "issue_count": len(issues),
    }


__all__ = ["SlotBox", "parse_named_text_slots", "validate_named_text_slots"]
