"""The image-style library must stay independent of native templates."""
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "templates/image_references"


def test_builtin_image_references_are_complete_and_separate():
    catalog = json.loads((LIBRARY / "registry.json").read_text(encoding="utf-8"))
    assert catalog["library_kind"] == "image_style_reference"
    assert catalog["native_template_library"] is False
    assert catalog["loading_policy"] == "index_then_selected_image"
    entries = catalog["templates"]
    assert len(entries) == 13
    ids = [entry["id"] for entry in entries]
    assert len(set(ids)) == 13
    assert {"defense_academic_blue_topnav", "defense_dark_blue_leftnav",
            "defense_burgundy_leftnav", "proposal_blue_white"}.issubset(ids)
    assert "afm_dark_blue" in ids
    native_policy = (ROOT / "templates/template_policy.json").read_text(encoding="utf-8")
    for entry in entries:
        assert "source_pptx" not in entry and "previous_image" not in entry
        assert "/" not in entry["source_filename"] and "\\" not in entry["source_filename"]
        assert not re.search(r"[A-Za-z]:[\\/]", json.dumps(entry, ensure_ascii=False))
        assert re.fullmatch(r"[a-z][a-z0-9_]*", entry["id"])
        assert f'"{entry["id"]}"' not in native_policy
        assert entry["slide_count"] > 0
        assert entry["version"] >= 1
        assert 5 < len(entry["style_summary"]) < 100
        for key in ("image", "preview"):
            path = LIBRARY / entry[key]
            assert path.parent == LIBRARY
            with Image.open(path) as im:
                im.verify()
        with Image.open(LIBRARY / entry["image"]) as im:
            assert list(im.size) == entry["image_size"]
    routing = (ROOT / "workflows/routing.md").read_text(encoding="utf-8")
    assert "templates/image_references/registry.json" in routing
    assert "not the native editable template library" in routing
    assert "Do not preload all template images" in routing
