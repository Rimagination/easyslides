from xml.etree import ElementTree as ET

from scripts.image_fit import apply_image_fit_policy, find_image_fit_violations


SVG_NS = "http://www.w3.org/2000/svg"


def _root(markup: str) -> ET.Element:
    return ET.fromstring(markup)


def test_contain_normalizes_direct_image_slot() -> None:
    root = _root(
        f'<svg xmlns="{SVG_NS}"><image x="0" y="0" width="100" height="40" '
        'preserveAspectRatio="none" data-slot="FIGURE" data-slot-kind="image"/></svg>'
    )

    report = apply_image_fit_policy(root, [{"slot_id": "FIGURE", "kind": "image", "image_fit": "contain"}])

    image = next(node for node in root.iter() if node.tag.endswith("image"))
    assert image.get("preserveAspectRatio") == "xMidYMid meet"
    assert image.get("data-easyslides-image-fit") == "contain"
    assert report["status"] == "pass"
    assert find_image_fit_violations(root, [{"slot_id": "FIGURE", "image_fit": "contain"}]) == []


def test_contain_flattens_imported_crop_wrapper() -> None:
    root = _root(
        f'<svg xmlns="{SVG_NS}"><g><svg x="10" y="20" width="200" height="80" '
        'viewBox="0.1 0.2 0.8 0.6" preserveAspectRatio="none">'
        '<image x="0" y="0" width="1" height="1" preserveAspectRatio="none" '
        'data-slot="FIGURE" data-slot-kind="image" href="figure.jpg"/>'
        '</svg></g></svg>'
    )

    report = apply_image_fit_policy(root, [{"slot_id": "FIGURE", "kind": "image", "image_fit": "contain"}])

    images = [node for node in root.iter() if node.tag.endswith("image")]
    assert len(images) == 1
    image = images[0]
    assert image.get("x") == "10"
    assert image.get("y") == "20"
    assert image.get("width") == "200"
    assert image.get("height") == "80"
    assert image.get("preserveAspectRatio") == "xMidYMid meet"
    assert report["flattened"] == ["FIGURE"]


def test_cover_is_allowed_but_stretch_is_explicit() -> None:
    root = _root(
        f'<svg xmlns="{SVG_NS}"><image preserveAspectRatio="none" '
        'data-slot="PHOTO" data-slot-kind="image"/></svg>'
    )
    apply_image_fit_policy(root, [{"slot_id": "PHOTO", "kind": "image", "image_fit": "cover"}])
    image = next(node for node in root.iter() if node.tag.endswith("image"))
    assert image.get("preserveAspectRatio") == "xMidYMid slice"
    assert find_image_fit_violations(root, [{"slot_id": "PHOTO", "image_fit": "cover"}]) == []


def test_contain_adds_subtle_frame_but_skips_full_canvas_background() -> None:
    root = _root(
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 1280 720">'
        '<image x="0" y="0" width="1280" height="720" data-slot="BG" data-slot-kind="image"/>'
        '<image x="80" y="120" width="420" height="240" data-slot="FIGURE" data-slot-kind="image"/>'
        '</svg>'
    )

    report = apply_image_fit_policy(root)

    frames = [node for node in root.iter() if node.get("data-easyslides-image-frame-for")]
    assert [node.get("data-easyslides-image-frame-for") for node in frames] == ["FIGURE"]
    assert report["framed"] == ["FIGURE"]
