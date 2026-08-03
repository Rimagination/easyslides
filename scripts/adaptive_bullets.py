"""Synchronize source-faithful bullet dots with bound text lines.

Some distilled pages preserve two or more colored dots from the source slide.
Those dots are meaningful only when the corresponding text has that many
visible lines. The template marks each dot group with
``data-easyslides-bullet-for`` and ``data-easyslides-bullet-index``; this module
removes unused groups after payload binding.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET


def _text_lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line for line in str(value or "").splitlines() if line.strip()]


def sync_adaptive_bullets(root: ET.Element, payload: dict[str, Any]) -> dict[str, Any]:
    """Remove bullet groups whose bound slot has fewer visible lines."""

    parents = {child: parent for parent in root.iter() for child in list(parent)}
    removed: list[dict[str, Any]] = []
    inspected = 0
    for node in list(root.iter()):
        slot = str(node.attrib.get("data-easyslides-bullet-for") or "").strip()
        if not slot:
            continue
        inspected += 1
        try:
            index = int(node.attrib.get("data-easyslides-bullet-index") or "1")
        except (TypeError, ValueError):
            continue
        if index < 1:
            continue
        line_count = len(_text_lines(payload.get(slot)))
        if index <= line_count:
            continue
        parent = parents.get(node)
        if parent is not None:
            parent.remove(node)
            removed.append({"slot": slot, "index": index, "line_count": line_count})

    return {
        "schema_version": "easyslides.adaptive_bullet_sync.v1",
        "status": "pass",
        "inspected": inspected,
        "removed": removed,
        "removed_count": len(removed),
    }
