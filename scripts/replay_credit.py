"""Render a legible bottom-right credit for an EasySlides recording."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys


def credit_fonts(text: str, font: Path | None) -> tuple[Path, Path]:
    if font is not None:
        if not font.is_file():
            raise ValueError(f"Credit font does not exist: {font}")
        return font, font
    if sys.platform == "win32":
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        normal = windows_fonts / "msyhbd.ttc"
        calligraphy = windows_fonts / "STXINGKA.TTF"
        if normal.is_file():
            return normal, calligraphy if calligraphy.is_file() else normal
    cjk_fonts = (
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )
    latin_fonts = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    )
    for candidate in cjk_fonts + (latin_fonts if text.isascii() else ()):
        if candidate.is_file():
            return candidate, candidate
    raise ValueError("No suitable credit font found. Pass --credit-font with a font that supports the text.")


def render_credit(
    destination: Path,
    *,
    text: str,
    frame_width: int,
    frame_height: int,
    style: str,
    accent: str | None,
    font_path: Path | None,
) -> tuple[int, int]:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    normal, calligraphy = credit_fonts(text, font_path)
    flourish = style == "flourish"
    if flourish and accent is None:
        match = re.search(r"@[\w.-]+", text)
        accent = match.group() if match else None

    base = max(7, min(round(frame_width * 24 / 1920), frame_height // 10))
    plain_ink = "#F8FFF5"
    runs = [(text, normal, base, plain_ink)]
    if flourish and accent:
        before, _, after = text.partition(accent)
        runs = [
            (before, normal, base, plain_ink),
            (accent, calligraphy, round(base * 1.4), "#FFD282"),
            (after, normal, base, plain_ink),
        ]
    scale = 3
    fonts = [ImageFont.truetype(str(path), size * scale) for _, path, size, _ in runs]
    advances = [font.getlength(value) for (value, _, _, _), font in zip(runs, fonts)]
    padding = max(6, base // 2 if not flourish else base // 3) * scale
    height = round(base * (2.15 if flourish else 1.85)) * scale
    baseline = round(base * 1.41) * scale
    art = Image.new("RGBA", (round(sum(advances) + 2 * padding), height))
    positions = [round(padding + sum(advances[:index])) for index in range(len(runs))]
    outer = max(1, round(base * .16)) * scale
    inner = max(1, round(base * .095)) * scale

    draw = ImageDraw.Draw(art)
    if flourish:
        for (value, _, _, _), font, x in zip(runs, fonts, positions):
            draw.text((x + scale, baseline + 3 * scale), value, font=font, anchor="ls",
                      fill="#152B25BF", stroke_width=outer, stroke_fill="#152B25BF")
        art = art.filter(ImageFilter.GaussianBlur(max(1, base * .05) * scale))
        draw = ImageDraw.Draw(art)
        if accent:
            start = positions[1] + scale
            stop = positions[1] + round(advances[1]) - scale
            y = baseline + round(base * .38) * scale
            draw.line([(start, y), ((start + stop) // 2, y + scale), (stop, y - scale)],
                      fill="#F5AA62", width=max(2, inner // 2))
        for (value, _, _, ink), font, x in zip(runs, fonts, positions):
            draw.text((x, baseline), value, font=font, anchor="ls", fill=ink,
                      stroke_width=outer, stroke_fill="#F7F9EF")
    else:
        draw.rounded_rectangle((0, 0, art.width - 1, art.height - 1), radius=max(2, base // 3) * scale,
                               fill="#152D28DB")

    for (value, _, _, ink), font, x in zip(runs, fonts, positions):
        draw.text((x, baseline), value, font=font, anchor="ls", fill=ink,
                  stroke_width=inner if flourish else 0, stroke_fill="#25453A")
    margin_x, margin_y = max(2, round(frame_width * .0125)), max(2, round(frame_height * .037))
    ratio = min(1 / scale, (frame_width - 2 * margin_x) / art.width,
                (frame_height - 2 * margin_y) / art.height)
    art.resize((max(1, round(art.width * ratio)), max(1, round(art.height * ratio))),
               Image.Resampling.LANCZOS).save(destination)
    return margin_x, margin_y
