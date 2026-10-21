"""Synthetic scan fixtures: a booklet, a damaged scan of it and shuffled rescans.

The text comes from Pride and Prejudice (public domain, Project Gutenberg).
Pages are drawn, then degraded the way a flatbed scanner and a bad day would:
skew, a dark scanner bed, noise, blur, stains and creases. Ground truth is
written next to the files so tests and the benchmark can score the matcher
against labels that the matcher never sees.
"""

from __future__ import annotations

import gzip
import json
import random
from importlib import resources
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PAGE_W, PAGE_H = 1000, 1414
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FORM_FIELDS = ["Name", "Account", "Date", "Amount", "Reference", "Approved by"]
FORM_NAMES = ["M. Bennet", "E. Darcy", "C. Bingley", "L. Wickham", "J. Collins", "G. Fitzwilliam"]


def _font(size: int, bold: bool = False, serif: bool = True) -> ImageFont.FreeTypeFont:
    name = ("DejaVuSerif" if serif else "DejaVuSans") + ("-Bold" if bold else "") + ".ttf"
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default(size)


def _paragraphs() -> list[str]:
    text = gzip.decompress(resources.files("darnleaf").joinpath("data/sample_text.txt.gz").read_bytes()).decode("utf-8")
    return [p for p in text.split("\n\n") if len(p.strip()) >= 25 or p.startswith("CHAPTER")]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _blank() -> Image.Image:
    return Image.new("L", (PAGE_W, PAGE_H), 255)


def _header(draw: ImageDraw.ImageDraw, number: int) -> None:
    small = _font(20, serif=False)
    title = "Pride and Prejudice" if number % 2 else "Volume One"
    x = 110 if number % 2 == 0 else PAGE_W - 110 - draw.textlength(title, font=small)
    draw.text((x, 70), title, font=small, fill=90)
    draw.line([(110, 108), (PAGE_W - 110, 108)], fill=150, width=1)
    draw.text((PAGE_W / 2 - 10, PAGE_H - 90), str(number), font=small, fill=60)


def _text_page(number: int, paras: list[str], cursor: int) -> tuple[Image.Image, int]:
    img = _blank()
    draw = ImageDraw.Draw(img)
    _header(draw, number)
    body, head = _font(23), _font(40, bold=True)
    y, width = 160, PAGE_W - 220
    while y < PAGE_H - 170:
        if cursor >= len(paras):
            cursor = 0
        para = paras[cursor]
        if para.startswith("CHAPTER"):
            if y > 160:
                break
            draw.text((PAGE_W / 2 - draw.textlength(para, font=head) / 2, y + 40), para, font=head, fill=20)
            y += 130
            cursor += 1
            continue
        lines = _wrap(draw, para, body, width - 36)
        room = (PAGE_H - 170 - y) // 34
        if room < 2:
            break
        for i, line in enumerate(lines[:room]):
            draw.text((110 + (36 if i == 0 else 0), y), line, font=body, fill=25)
            y += 34
        if len(lines) > room:
            paras[cursor] = " ".join(lines[room:])
            break
        y += 14
        cursor += 1
    return img, cursor


def _figure_page(number: int, rng: random.Random) -> Image.Image:
    img = _blank()
    draw = ImageDraw.Draw(img)
    _header(draw, number)
    cx, cy = rng.randint(380, 620), rng.randint(520, 760)
    for k in range(rng.randint(6, 11)):
        r = 60 + k * rng.randint(28, 40)
        draw.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], outline=30 + k * 12, width=rng.randint(2, 5))
    for _ in range(rng.randint(40, 90)):
        x0, y0 = rng.randint(130, 860), rng.randint(180, 1100)
        draw.line([(x0, y0), (x0 + rng.randint(-90, 90), y0 + rng.randint(30, 120))], fill=rng.randint(40, 140), width=2)
    draw.text((130, 1180), f"Plate {number // 10}. A scene at the assembly rooms.", font=_font(26), fill=40)
    return img


def _form_page(number: int, which: int) -> Image.Image:
    img = _blank()
    draw = ImageDraw.Draw(img)
    _header(draw, number)
    draw.text((110, 170), "REMITTANCE SLIP", font=_font(44, bold=True, serif=False), fill=20)
    label, value = _font(24, serif=False), _font(26)
    for i, name in enumerate(FORM_FIELDS):
        y = 300 + i * 120
        draw.text((110, y), name, font=label, fill=70)
        draw.rectangle([380, y - 10, PAGE_W - 110, y + 50], outline=90, width=2)
        text = [FORM_NAMES[which], f"{4000 + which * 137 + i}", f"1{which}/0{i + 1}/1813", f"{120 + which * 35}.50", f"R-{which}{i}{which * 7}", FORM_NAMES[(which + 2) % 6]][i]
        draw.text((396, y), text, font=value, fill=15)
    return img


def _foreign_paragraphs(rng: random.Random) -> list[str]:
    """Text that looks like the booklet's but says something else: words shuffled within each paragraph."""
    out = []
    for para in _paragraphs()[200:230]:
        words = para.split()
        rng.shuffle(words)
        out.append(" ".join(words))
    return out


def make_booklet(pages: int = 80, seed: int = 1) -> list[Image.Image]:
    """Clean pages: text, chapter openings, figures, six near-identical forms and a blank."""
    rng = random.Random(seed)
    paras, cursor, out = _paragraphs(), 0, []
    forms = set(range(30, 36))
    for number in range(1, pages + 1):
        if number == 2:
            out.append(_blank())
        elif number in forms:
            out.append(_form_page(number, number - 30))
        elif number % 11 == 0:
            out.append(_figure_page(number, rng))
        else:
            page, cursor = _text_page(number, paras, cursor)
            out.append(page)
    return out


def _stain(img: Image.Image, rng: random.Random) -> Image.Image:
    layer = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(layer)
    cx, cy = rng.randint(250, 750), rng.randint(350, 1100)
    for k in range(3):
        r = rng.randint(110, 200) - k * 20
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=110 - k * 30, width=rng.randint(8, 16))
    draw.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=35)
    layer = layer.filter(ImageFilter.GaussianBlur(6))
    dark = np.asarray(img, dtype=np.float32) - np.asarray(layer, dtype=np.float32) * 0.9
    return Image.fromarray(np.clip(dark, 0, 255).astype(np.uint8))


def damage(img: Image.Image, rng: random.Random) -> Image.Image:
    """A coffee ring, a crease and a smear: the reason the page needs replacing."""
    img = _stain(img, rng)
    draw = ImageDraw.Draw(img)
    y = rng.randint(400, 1000)
    draw.line([(0, y), (PAGE_W, y + rng.randint(-40, 40))], fill=120, width=3)
    smear = img.crop((100, 300, 900, 380)).filter(ImageFilter.GaussianBlur(7))
    img.paste(smear, (100, rng.randint(300, 1000)))
    return img


def scan(img: Image.Image, rng: random.Random, *, skew: float = 1.2, bed: bool = True) -> Image.Image:
    """Photograph the page the way a flatbed would: skew, margin, noise, blur, JPEG-ready."""
    angle = rng.uniform(-skew, skew)
    scale = rng.uniform(0.96, 1.04)
    w, h = int(PAGE_W * scale), int(PAGE_H * scale)
    page = img.resize((w, h), Image.BICUBIC).rotate(angle, expand=True, fillcolor=255, resample=Image.BICUBIC)
    bg = rng.randint(25, 70) if bed else 255
    canvas = Image.new("L", (PAGE_W + 120, PAGE_H + 120), bg)
    canvas.paste(page, (rng.randint(0, 120 + PAGE_W - page.width), rng.randint(0, 120 + PAGE_H - page.height)))
    arr = np.asarray(canvas, dtype=np.float32)
    ys, xs = np.mgrid[0 : arr.shape[0], 0 : arr.shape[1]]
    shade = 1 - rng.uniform(0.05, 0.18) * ((xs / arr.shape[1] - rng.random()) ** 2 + (ys / arr.shape[0] - rng.random()) ** 2)
    arr = arr * shade * rng.uniform(0.9, 1.0) + np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(3, 7), arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.1)))
    if bed:
        pad = rng.randint(0, 40)
        out = out.crop((pad, pad, out.width - rng.randint(0, 40), out.height - rng.randint(0, 40)))
    return out.convert("RGB")


def save_pdf(images: list[Image.Image], path: Path, quality: int = 78) -> None:
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=150, quality=quality)


def make_case(out: Path, pages: int = 80, seed: int = 1, replacements: int = 8) -> dict:
    """Write original.pdf, rescans/*.jpg and truth.json under out and return the truth."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "rescans").mkdir(exist_ok=True)
    rng = random.Random(seed)
    clean = make_booklet(pages, seed)
    # Two near-identical forms and the blank verso are deliberately among the damaged pages.
    pool = [p for p in range(1, pages + 1) if p not in (2, 30, 31)]
    hurt = sorted(rng.sample(pool, replacements - 3) + [2, 31, 33])
    scans = []
    for index, page in enumerate(clean, start=1):
        base = page
        if index in hurt:
            base = page.point(lambda v: int(v * 0.93)) if index == 2 else damage(page.copy(), rng)
        scans.append(scan(base, rng, skew=0.8))
    save_pdf(scans, out / "original.pdf")
    truth: dict[str, int | None] = {}
    turned: dict[str, int] = {}
    order = hurt[:]
    rng.shuffle(order)
    for k, index in enumerate(order, start=1):
        fresh = scan(clean[index - 1], rng, skew=1.6)
        turn = rng.choice([0, 0, 90, 180, 270]) if index != 2 else 0
        if turn:
            fresh = fresh.rotate(turn, expand=True)
        name = f"rescan-{k:02d}.jpg"
        turned[name] = turn
        fresh.save(out / "rescans" / name, quality=82)
        truth[name] = index
    decoy_page, _ = _text_page(pages + 7, _foreign_paragraphs(rng), 0)
    decoy = scan(decoy_page, rng, skew=1.6)
    decoy.save(out / "rescans" / f"rescan-{len(order) + 1:02d}.jpg", quality=82)
    truth[f"rescan-{len(order) + 1:02d}.jpg"] = None
    (out / "truth.json").write_text(json.dumps({"pages": pages, "seed": seed, "truth": truth, "turned_ccw": turned}, indent=2))
    return truth
