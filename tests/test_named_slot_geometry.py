from __future__ import annotations

import json
from pathlib import Path


def _write_template(root: Path, svg: str) -> Path:
    (root / "functional_variants" / "toc").mkdir(parents=True)
    (root / "functional_page_variants.json").write_text(
        json.dumps(
            {
                "schema_version": "easyslides.functional_page_variants.v1",
                "groups": {
                    "toc": {
                        "default_variant": "toc_test",
                        "variants": [
                            {
                                "variant_id": "toc_test",
                                "preview_svg": "functional_variants/toc/toc_test.svg",
                                "slots": ["TITLE", "DESC"],
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    path = root / "functional_variants" / "toc" / "toc_test.svg"
    path.write_text(svg, encoding="utf-8")
    return root


def _svg(first_box: str, second_box: str) -> str:
    return f'''<svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
      <text data-pptx-textbox="true" data-pptx-box-x="{first_box.split(',')[0]}" data-pptx-box-y="{first_box.split(',')[1]}" data-pptx-box-w="{first_box.split(',')[2]}" data-pptx-box-h="{first_box.split(',')[3]}" data-slot="TITLE">标题</text>
      <text data-pptx-textbox="true" data-pptx-box-x="{second_box.split(',')[0]}" data-pptx-box-y="{second_box.split(',')[1]}" data-pptx-box-w="{second_box.split(',')[2]}" data-pptx-box-h="{second_box.split(',')[3]}" data-slot="DESC">说明</text>
    </svg>'''


def test_named_slot_geometry_accepts_separated_slots(tmp_path: Path) -> None:
    from scripts.functional_page_variant_adapter import select_functional_variant

    template = _write_template(tmp_path, _svg("100,100,300,50", "100,180,300,30"))
    selection = select_functional_variant(template, "toc")
    assert selection["variant"]["variant_id"] == "toc_test"


def test_named_slot_geometry_rejects_overlapping_slots(tmp_path: Path) -> None:
    from scripts.functional_page_variant_adapter import select_functional_variant

    template = _write_template(tmp_path, _svg("100,100,300,50", "100,125,300,30"))
    try:
        select_functional_variant(template, "toc")
    except ValueError as exc:
        assert "NAMED-SLOT-TEXT-OVERLAP" not in str(exc)
        assert "overlap" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("overlapping functional variant was selected")
