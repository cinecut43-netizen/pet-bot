"""Генерирует временную графику-заглушку для питомцев.

Это не финальный арт, а «скелет» для художника: показывает, какие файлы
нужны, какого они размера и как рендерер их складывает. Настоящие картинки
кладутся поверх с теми же именами — код менять не придётся.

Запуск:  python tools/make_placeholder_art.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent / "assets"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
W, H = MANIFEST["canvas"]
S = 2  # рисуем в 2x и уменьшаем — так края получаются сглаженными

LINE = (70, 52, 48, 255)
WHITE = (255, 255, 255, 255)
PINK = (255, 170, 180, 255)


def canvas(w: int = W, h: int = H) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((img.width // S, img.height // S), Image.LANCZOS).save(path)


def s(*xy: float) -> list[float]:
    return [v * S for v in xy]


# ---------- виды ----------

def species_shapes(draw: ImageDraw.ImageDraw, sp: str, fill) -> None:
    """Силуэт питомца. Голова и тело общие для всех видов, чтобы одежда
    по умолчанию садилась одинаково; отличаются уши и хвост."""
    if sp == "fox":
        draw.polygon(s(330, 420, 470, 330, 450, 450, 360, 470), fill=fill)  # хвост
        draw.polygon(s(150, 150, 165, 30, 245, 110), fill=fill)
        draw.polygon(s(362, 150, 347, 30, 267, 110), fill=fill)
    elif sp == "bunny":
        draw.ellipse(s(170, 0, 230, 150), fill=fill)
        draw.ellipse(s(282, 0, 342, 150), fill=fill)
        draw.ellipse(s(335, 400, 385, 450), fill=fill)  # хвостик
    else:  # cat
        draw.polygon(s(155, 140, 170, 50, 235, 100), fill=fill)
        draw.polygon(s(357, 140, 342, 50, 277, 100), fill=fill)
        draw.line(s(340, 440, 420, 420, 440, 350), fill=fill, width=26 * S, joint="curve")
    draw.ellipse(s(160, 255, 352, 470), fill=fill)  # тело
    draw.ellipse(s(170, 440, 235, 485), fill=fill)  # лапки
    draw.ellipse(s(277, 440, 342, 485), fill=fill)
    draw.ellipse(s(141, 80, 371, 300), fill=fill)  # голова


def make_species(sp: str) -> None:
    out = ROOT / "species" / sp

    # body.png — оттенки серого; рендерер умножает их на выбранный цвет
    body, d = canvas()
    species_shapes(d, sp, (235, 235, 235, 255))
    shade = Image.new("RGBA", body.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.ellipse(s(160, 380, 352, 520), fill=(190, 190, 190, 255))
    # тень внизу тела — только там, где есть сам силуэт
    body.paste(shade, (0, 0), ImageChops.multiply(shade.split()[3], body.split()[3]))
    save(body, out / "body.png")

    # extras.png — неокрашиваемые детали: животик, внутренние уши, нос
    ex, d = canvas()
    d.ellipse(s(205, 310, 307, 440), fill=(255, 255, 255, 200))
    if sp == "cat":
        d.polygon(s(170, 130, 178, 75, 220, 105), fill=PINK)
        d.polygon(s(342, 130, 334, 75, 292, 105), fill=PINK)
    elif sp == "fox":
        d.polygon(s(165, 140, 172, 60, 228, 108), fill=WHITE)
        d.polygon(s(347, 140, 340, 60, 284, 108), fill=WHITE)
        d.ellipse(s(196, 195, 316, 290), fill=(255, 255, 255, 230))  # мордочка
        d.polygon(s(445, 360, 470, 330, 462, 400), fill=WHITE)  # кончик хвоста
    elif sp == "bunny":
        d.ellipse(s(185, 20, 215, 135), fill=PINK)
        d.ellipse(s(297, 20, 327, 135), fill=PINK)
    d.ellipse(s(246, 222, 266, 236), fill=(240, 120, 130, 255))  # нос
    save(ex, out / "extras.png")

    # lines.png — контур, вычисленный из силуэта (без внутренних линий)
    sil, d = canvas()
    species_shapes(d, sp, WHITE)
    m = sil.split()[3]
    grown = m.filter(ImageFilter.MaxFilter(9 * S + 1))
    edge = ImageChops.subtract(grown, m)
    line = Image.new("RGBA", m.size, LINE)
    line.putalpha(edge)
    save(line, out / "lines.png")


# ---------- выражения (общие для всех видов, якорь face) ----------
# Небольшой холст 240x160 с центром в якоре face.

def make_expressions() -> None:
    ew, eh = 240, 160
    cx, cy = ew / 2, eh / 2
    lx, rx, ey = cx - 42, cx + 42, cy - 10

    def blush(d):
        d.ellipse(s(lx - 30, ey + 25, lx + 2, ey + 42), fill=(255, 140, 150, 110))
        d.ellipse(s(rx - 2, ey + 25, rx + 30, ey + 42), fill=(255, 140, 150, 110))

    # happy
    img, d = canvas(ew, eh)
    for x in (lx, rx):
        d.arc(s(x - 16, ey - 12, x + 16, ey + 14), 200, 340, fill=LINE, width=6 * S)
    d.chord(s(cx - 18, cy + 32, cx + 18, cy + 62), 0, 180, fill=(150, 60, 70, 255))
    blush(d)
    save(img, ROOT / "expressions" / "happy" / "default.png")

    # ok
    img, d = canvas(ew, eh)
    for x in (lx, rx):
        d.ellipse(s(x - 10, ey - 12, x + 10, ey + 12), fill=LINE)
        d.ellipse(s(x - 4, ey - 8, x + 2, ey - 2), fill=WHITE)
    d.arc(s(cx - 14, cy + 30, cx + 14, cy + 50), 20, 160, fill=LINE, width=5 * S)
    save(img, ROOT / "expressions" / "ok" / "default.png")

    # sad — грустный, но не несчастный
    img, d = canvas(ew, eh)
    for x, k in ((lx, -1), (rx, 1)):
        d.ellipse(s(x - 10, ey - 6, x + 10, ey + 14), fill=LINE)
        d.ellipse(s(x - 4, ey - 2, x + 2, ey + 4), fill=WHITE)
        d.line(s(x - 16, ey - 18 - 6 * k, x + 16, ey - 18 + 6 * k), fill=LINE, width=5 * S)
    d.arc(s(cx - 14, cy + 40, cx + 14, cy + 60), 200, 340, fill=LINE, width=5 * S)
    save(img, ROOT / "expressions" / "sad" / "default.png")

    # sleepy
    img, d = canvas(ew, eh)
    for x in (lx, rx):
        d.arc(s(x - 16, ey - 14, x + 16, ey + 10), 20, 160, fill=LINE, width=6 * S)
    d.ellipse(s(cx - 8, cy + 36, cx + 8, cy + 52), fill=(150, 60, 70, 255))
    d.text(s(rx + 40, 0), "z", fill=LINE, font_size=40 * S)
    d.text(s(rx + 62, -10), "z", fill=LINE, font_size=28 * S)
    save(img, ROOT / "expressions" / "sleepy" / "default.png")


# ---------- черты (якорь face) ----------

def make_traits() -> None:
    ew, eh = 240, 160
    cx, cy = ew / 2, eh / 2
    img, d = canvas(ew, eh)
    for x0 in (cx - 62, cx + 50):
        for dx, dy in ((0, 0), (12, 6), (4, 14)):
            d.ellipse(s(x0 + dx, cy + 18 + dy, x0 + dx + 6, cy + 24 + dy), fill=(150, 90, 60, 200))
    save(img, ROOT / "traits" / "freckles" / "default.png")

    img, d = canvas(ew, eh)
    d.ellipse(s(cx + 12, cy - 44, cx + 76, cy + 18), fill=(80, 55, 45, 110))
    save(img, ROOT / "traits" / "eyepatch" / "default.png")

    img, d = canvas(ew, eh)
    r1, r2, x, y = 14, 6, cx, cy - 66
    pts = []
    for i in range(10):
        r = r1 if i % 2 == 0 else r2
        a = math.pi / 2 + i * math.pi / 5
        pts += [x + r * math.cos(a), y - r * math.sin(a)]
    d.polygon(s(*pts), fill=(255, 220, 90, 255))
    save(img, ROOT / "traits" / "star" / "default.png")


# ---------- одежда (default.png центрируется в якоре своего слота) ----------

def make_items() -> None:
    # Шапочка: якорь head (256, 92)
    img, d = canvas(240, 140)
    d.chord(s(20, 30, 220, 190), 180, 360, fill=(90, 140, 220, 255), outline=LINE, width=4 * S)
    d.rounded_rectangle(s(14, 96, 226, 124), radius=12 * S, fill=(70, 115, 200, 255), outline=LINE, width=4 * S)
    d.ellipse(s(102, 4, 138, 40), fill=WHITE, outline=LINE, width=4 * S)
    save(img, ROOT / "items" / "beanie" / "default.png")

    # Бантик
    img, d = canvas(160, 100)
    d.polygon(s(80, 50, 15, 15, 15, 85), fill=(240, 90, 120, 255), outline=LINE, width=4 * S)
    d.polygon(s(80, 50, 145, 15, 145, 85), fill=(240, 90, 120, 255), outline=LINE, width=4 * S)
    d.ellipse(s(64, 34, 96, 66), fill=(220, 60, 100, 255), outline=LINE, width=4 * S)
    save(img, ROOT / "items" / "bow" / "default.png")

    # Шарфик: якорь neck (256, 300)
    img, d = canvas(240, 160)
    d.rounded_rectangle(s(20, 20, 220, 60), radius=18 * S, fill=(230, 80, 70, 255), outline=LINE, width=4 * S)
    d.rounded_rectangle(s(140, 40, 180, 140), radius=12 * S, fill=(230, 80, 70, 255), outline=LINE, width=4 * S)
    for y in (70, 95, 120):
        d.line(s(142, y, 178, y), fill=(255, 220, 210, 255), width=5 * S)
    save(img, ROOT / "items" / "scarf" / "default.png")

    # Очки: якорь face (256, 200), глаза в ±42 по x и -10 по y
    img, d = canvas(240, 160)
    cx, ey = 120, 70
    for x in (cx - 42, cx + 42):
        d.ellipse(s(x - 30, ey - 28, x + 30, ey + 28), fill=(200, 230, 255, 70), outline=LINE, width=6 * S)
    d.line(s(cx - 12, ey - 4, cx + 12, ey - 4), fill=LINE, width=6 * S)
    save(img, ROOT / "items" / "glasses" / "default.png")

    # Футболка: якорь body (256, 385)
    img, d = canvas(260, 200)
    d.polygon(s(30, 40, 90, 10, 170, 10, 230, 40, 215, 85, 195, 75, 195, 190, 65, 190, 65, 75, 45, 85),
              fill=(120, 200, 120, 235), outline=LINE, width=4 * S)
    d.ellipse(s(110, 90, 150, 130), fill=(255, 255, 255, 200))
    save(img, ROOT / "items" / "tshirt" / "default.png")


if __name__ == "__main__":
    for sp in MANIFEST["species"]:
        make_species(sp)
    make_expressions()
    make_traits()
    make_items()
    print("Заглушки сгенерированы в", ROOT)
