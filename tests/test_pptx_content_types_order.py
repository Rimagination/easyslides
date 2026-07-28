from __future__ import annotations

import xml.etree.ElementTree as ET

from scripts.svg_to_pptx.pptx_builder import (
    _add_default_content_type,
    _insert_default_content_types,
)


BASE_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
</Types>
"""


def _local_names(xml: str) -> list[str]:
    return [child.tag.rsplit("}", 1)[-1] for child in ET.fromstring(xml)]


def test_insert_default_content_types_keeps_schema_order() -> None:
    updated = _insert_default_content_types(
        BASE_CONTENT_TYPES,
        [
            '  <Default Extension="jpg" ContentType="image/jpeg"/>',
            '  <Default Extension="png" ContentType="image/png"/>',
        ],
    )

    names = _local_names(updated)
    first_override = names.index("Override")
    assert all(name == "Default" for name in names[:first_override])
    assert names[first_override:] == ["Override"]


def test_add_default_content_type_is_ordered_and_idempotent() -> None:
    updated = _add_default_content_type(BASE_CONTENT_TYPES, "jpg", "image/jpeg")
    repeated = _add_default_content_type(updated, "jpg", "image/jpeg")

    assert repeated == updated
    assert updated.count('Extension="jpg"') == 1
    assert _local_names(updated) == ["Default", "Default", "Default", "Override"]
