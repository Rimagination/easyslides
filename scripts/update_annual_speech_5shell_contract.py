"""Synchronize the 5-shell annual speech slot contract with its SVG slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def text_slot(slot_id: str, role: str, max_chars: int, max_lines: int = 1) -> dict[str, object]:
    return {
        "slot_id": slot_id,
        "role": role,
        "kind": "text",
        "max_lines": max_lines,
        "max_chars_per_line": max_chars,
    }


def image_slot(slot_id: str, role: str | None = None) -> dict[str, object]:
    return {
        "slot_id": slot_id,
        "role": role or slot_id.lower(),
        "kind": "image",
        "image_fit": "contain",
    }


def fit(default: int, minimum: int, chars: int, action: str = "split", lines: int = 2) -> dict[str, object]:
    return {
        "default_font_size_px": default,
        "min_font_size_px": minimum,
        "line_height": 1.2,
        "max_chars_per_line_zh": chars,
        "overflow_action": action,
        "max_lines": lines,
    }


def run(root: Path) -> None:
    if root.name != "annual_speech_2025_distilled_5shell":
        raise ValueError(f"refusing to edit unexpected template directory: {root}")
    path = root / "layouts.json"
    layouts = json.loads(path.read_text(encoding="utf-8"))

    layouts["slot_models"] = {
        "chapter": [
            *[text_slot(f"CHAPTER_TITLE_{i:02d}", f"chapter_title_{i:02d}", 16, 2) for i in range(1, 5)],
            *[text_slot(f"CHAPTER_DESC_{i:02d}", f"chapter_desc_{i:02d}", 16, 2) for i in range(1, 5)],
            text_slot("YEAR", "year", 4, 1),
            image_slot("IMAGE_01"),
            image_slot("IMAGE_02"),
            image_slot("IMAGE_03"),
        ],
        "content": [
            text_slot("KEY_MESSAGE", "key_message", 30, 2),
            text_slot("PAGE_TITLE", "page_title", 18, 2),
            text_slot("PRESENTER", "presenter", 24, 1),
            text_slot("DATE", "date", 16, 1),
            image_slot("IMAGE_01"),
            image_slot("IMAGE_02"),
            image_slot("IMAGE_03"),
        ],
        "cover": [
            text_slot("TITLE", "title", 18, 2),
            text_slot("SUBTITLE", "subtitle", 16, 2),
            text_slot("PRESENTER", "presenter", 24, 1),
            text_slot("DATE", "date", 16, 1),
            image_slot("HERO_IMAGE"),
            image_slot("IMAGE_02"),
        ],
        "ending": [
            text_slot("CLOSING_TITLE", "closing_title", 18, 2),
            text_slot("CLOSING_SUBTITLE", "closing_subtitle", 16, 2),
            text_slot("PRESENTER", "presenter", 24, 1),
            text_slot("DATE", "date", 16, 1),
            image_slot("IMAGE_01"),
            image_slot("IMAGE_02"),
        ],
        "toc": [
            *[text_slot(f"TOC_ITEM_{i:02d}", f"toc_item_{i:02d}", 18, 2) for i in range(1, 9)],
            image_slot("IMAGE_01"),
        ],
    }

    role_defaults: dict[str, dict[str, object]] = {
        "title": fit(48, 32, 18),
        "subtitle": fit(24, 16, 28),
        "presenter": fit(20, 14, 24, "truncate", 1),
        "date": fit(20, 14, 16, "truncate", 1),
        "key_message": fit(20, 14, 30),
        "page_title": fit(30, 22, 20),
        "closing_title": fit(56, 38, 12),
        "closing_subtitle": fit(24, 16, 24),
        "year": fit(32, 24, 4, "truncate", 1),
    }
    for i in range(1, 9):
        role_defaults[f"toc_item_{i:02d}"] = fit(26, 18, 18)
    for i in range(1, 5):
        role_defaults[f"chapter_title_{i:02d}"] = fit(40, 28, 16)
        role_defaults[f"chapter_desc_{i:02d}"] = fit(22, 15, 30)

    policy = layouts.get("text_fit_policy") or {}
    policy["role_defaults"] = role_defaults
    layouts["text_fit_policy"] = policy
    path.write_text(json.dumps(layouts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    run(args.root)


if __name__ == "__main__":
    main()
