import json
from pathlib import Path

from scripts.template_palette import (
    materialize_template_palette,
    palette_color_replacements,
    read_palette_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
DEFENSE01 = ROOT / "templates" / "layouts" / "defense_leftnav"
DEFENSE02 = ROOT / "templates" / "layouts" / "defense_topnav"


def test_defense_leftnav_palette_catalog_defines_academic_theme_families():
    catalog = read_palette_catalog(DEFENSE01)

    assert catalog["schema_version"] == "easyslides.theme_palettes.v1"
    assert catalog["template_id"] == "defense_leftnav"
    assert catalog["default_palette"] == "wine"
    assert set(catalog["palettes"]) == {
        "wine",
        "academic_blue",
        "academic_purple",
        "academic_green",
    }

    for palette in catalog["palettes"].values():
        assert set(palette["colors"]) >= {
            "primary",
            "primary_dark",
            "soft_surface",
            "border",
            "emphasis_text",
        }

    replacements = palette_color_replacements(catalog, "academic_blue")
    assert replacements == {
        "#8B0012": "#183A6A",
        "#68000D": "#10284A",
        "#F8F2F3": "#F2F5FA",
        "#D9C7CA": "#C8D4E3",
        "#3A0008": "#081B33",
    }


def test_materialize_template_palette_recolors_svgs_and_style_sidecars(tmp_path):
    output_dir = tmp_path / "defense_leftnav_academic_blue"

    written = materialize_template_palette(DEFENSE01, "academic_blue", output_dir)

    assert output_dir / "03_content.svg" in written
    content_svg = (output_dir / "03_content.svg").read_text(encoding="utf-8")
    assert "#183A6A" in content_svg
    assert "#10284A" in content_svg
    assert "#F2F5FA" in content_svg
    assert "#081B33" in content_svg
    assert "#8B0012" not in content_svg
    assert "#68000D" not in content_svg
    assert "#595959" in content_svg
    assert "#FFFFFF" in content_svg

    components = json.loads((output_dir / "component_styles.json").read_text(encoding="utf-8"))
    assert components["tokens"]["primary"] == "#183A6A"
    assert components["tokens"]["primary_dark"] == "#10284A"
    assert components["tokens"]["soft_surface"] == "#F2F5FA"
    assert components["tokens"]["border"] == "#C8D4E3"
    assert components["text_box_styles"]["takeaway_bar"]["text_color"] == "#081B33"

    nav = json.loads((output_dir / "navigation_states.json").read_text(encoding="utf-8"))
    assert nav["active_band_template"]["fill"] == "#183A6A"
    assert nav["active_fold_template"]["fill"] == "#10284A"
    assert nav["colors"]["active_band"] == "#183A6A"
    assert nav["colors"]["active_pointer"] == "#10284A"


def test_defense_topnav_palette_catalog_and_materialization_support_declared_themes(tmp_path):
    catalog = read_palette_catalog(DEFENSE02)

    assert catalog["schema_version"] == "easyslides.theme_palettes.v1"
    assert catalog["template_id"] == "defense_topnav"
    assert catalog["default_palette"] == "academic_blue"
    assert set(catalog["palettes"]) == {
        "academic_blue",
        "wine",
        "academic_purple",
        "academic_green",
        "thesis_navy_v4",
    }
    assert catalog["palettes"]["thesis_navy_v4"]["colors"]["primary"] == "#0A3476"
    assert catalog["palettes"]["thesis_navy_v4"]["colors"]["accent"] == "#1C8B92"
    assert catalog["palettes"]["thesis_navy_v4"]["colors"]["body_text"] == "#000000"

    output_dir = tmp_path / "defense_topnav_wine"
    written = materialize_template_palette(DEFENSE02, "wine", output_dir)

    assert output_dir / "03_content.svg" in written
    content_svg = (output_dir / "03_content.svg").read_text(encoding="utf-8")
    assert "#8B0012" in content_svg
    assert "#F8F2F3" in content_svg
    assert "#183A6A" not in content_svg
    assert "#E7E6E6" not in content_svg
    assert "#FFFFFF" in content_svg

    components = json.loads((output_dir / "component_styles.json").read_text(encoding="utf-8"))
    assert components["tokens"]["colors"]["primary"] == "#8B0012"
    assert components["tokens"]["colors"]["soft_surface"] == "#F8F2F3"
    assert components["composition_primitives"]["figure_frame"]["stroke"] == "#D9C7CA"
    assert components["composition_primitives"]["callout"]["text_fill"] == "#3A0008"

    nav = json.loads((output_dir / "navigation_states.json").read_text(encoding="utf-8"))
    assert nav["sections"][0]["active_tab"]["fill"] == "#FFFFFF"
    assert nav["theme_color_roles"]["primary"] == "#8B0012"
