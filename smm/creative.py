"""Creative Studio (images): renders an on-brand 1080x1080 post card with Pillow. $0, no design tool."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import Config

SIZE = 1080
MARGIN = 90


def _font(path: str | None, size: int):
    if path and Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)  # Pillow >= 10.1 ships a scalable default font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit(draw, text, font_path, max_size, min_size, width, max_height, spacing=1.15):
    size = max_size
    while size >= min_size:
        font = _font(font_path, size)
        lines = _wrap(draw, text, font, width)
        if len(lines) * size * spacing <= max_height:
            return font, lines, size
        size -= 4
    font = _font(font_path, min_size)
    return font, _wrap(draw, text, font, width), min_size


def render_card(cfg: Config, headline: str, subtext: str, out_path: Path) -> Path:
    design = cfg.section("design")
    bg = design.get("background", "#0F172A")
    fg = design.get("text", "#F8FAFC")
    accent = design.get("accent", "#22C55E")
    font_path = design.get("font_path") or None
    bold_path = design.get("bold_font_path") or font_path

    img = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)
    width = SIZE - 2 * MARGIN

    draw.rectangle([MARGIN, MARGIN, MARGIN + 140, MARGIN + 16], fill=accent)

    h_font, h_lines, h_size = _fit(draw, headline, bold_path, 104, 52, width, 520)
    y = MARGIN + 90
    for line in h_lines:
        draw.text((MARGIN, y), line, font=h_font, fill=fg)
        y += int(h_size * 1.15)

    y += 40
    s_font, s_lines, s_size = _fit(draw, subtext, font_path, 46, 30, width, SIZE - y - 200)
    for line in s_lines:
        draw.text((MARGIN, y), line, font=s_font, fill=fg)
        y += int(s_size * 1.3)

    footer_font = _font(bold_path, 36)
    company = (cfg.section("company").get("name") or "").strip()
    handle = (cfg.section("rules").get("handle") or "").strip()
    footer_y = SIZE - MARGIN - 40
    draw.line([MARGIN, footer_y - 30, SIZE - MARGIN, footer_y - 30], fill=accent, width=3)
    draw.text((MARGIN, footer_y), company, font=footer_font, fill=fg)
    if handle:
        w = draw.textlength(handle, font=footer_font)
        draw.text((SIZE - MARGIN - w, footer_y), handle, font=footer_font, fill=accent)

    logo = design.get("logo_path")
    if logo and Path(logo).exists():
        mark = Image.open(logo).convert("RGBA")
        mark.thumbnail((140, 140))
        img.paste(mark, (SIZE - MARGIN - mark.width, MARGIN - 20), mark)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path
