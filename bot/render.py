"""Сборка картинки питомца из слоёв.

Порядок слоёв (снизу вверх):
    фон → тело (окрашивается) → детали → черты → контур → выражение → одежда по слотам

Как ищется файл слоя (например, вещь «beanie» на виде «bunny»):
    1. items/beanie/bunny.png   — нарисован специально под этот вид, холст 512×512
    2. items/beanie/default.png — общий вариант, центрируется в якоре слота вида
Так художник рисует вещь один раз, а для видов, где она «не села»,
дорисовывает отдельный файл — без правок кода.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


@dataclass(frozen=True)
class Look:
    species: str
    color: str
    mood: str
    traits: tuple[str, ...] = field(default_factory=tuple)
    items: tuple[str, ...] = field(default_factory=tuple)


class Renderer:
    def __init__(self, assets_dir: Path, cache_dir: Path):
        self.assets = Path(assets_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = json.loads((self.assets / "manifest.json").read_text(encoding="utf-8"))
        self.size = tuple(self.manifest["canvas"])

    # ---------- справочник ----------

    @property
    def species(self) -> dict:
        return self.manifest["species"]

    @property
    def colors(self) -> dict:
        return self.manifest["colors"]

    @property
    def traits(self) -> dict:
        return self.manifest["traits"]

    @property
    def items(self) -> dict:
        return self.manifest["items"]

    def item_slot(self, item_id: str) -> str:
        return self.items[item_id]["slot"]

    # ---------- кэш ----------

    def cache_key(self, look: Look) -> str:
        """Ключ зависит от версии графики: поменяли арт — поднимите version в manifest.json."""
        slots = self.manifest["slot_order"]
        items = sorted(look.items, key=lambda i: slots.index(self.item_slot(i)))
        raw = "|".join([
            f"v{self.manifest['version']}", look.species, look.color, look.mood,
            ",".join(sorted(look.traits)), ",".join(items),
        ])
        return hashlib.sha1(raw.encode()).hexdigest()[:20]

    def render_png(self, look: Look) -> bytes:
        """PNG-байты картинки; результат кэшируется на диске."""
        path = self.cache_dir / f"{self.cache_key(look)}.png"
        if path.exists():
            return path.read_bytes()
        buf = io.BytesIO()
        self.compose(look).save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return data

    def grid_key(self, looks: list[Look]) -> str:
        raw = ";".join(self.cache_key(l) for l in looks)
        return hashlib.sha1(raw.encode()).hexdigest()[:20]

    def grid_png(self, looks: list[Look], cols: int = 3, cell: int = 256) -> bytes:
        """Несколько питомцев на одной картинке — для выбора вида и цвета."""
        path = self.cache_dir / f"grid_{self.grid_key(looks)}.png"
        if path.exists():
            return path.read_bytes()
        rows = (len(looks) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell, rows * cell), tuple(self.manifest["background"]))
        for i, look in enumerate(looks):
            tile = self.compose(look).resize((cell, cell), Image.LANCZOS)
            sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
        buf = io.BytesIO()
        sheet.save(buf, format="PNG", optimize=True)
        path.write_bytes(buf.getvalue())
        return buf.getvalue()

    # ---------- сборка ----------

    def compose(self, look: Look) -> Image.Image:
        if look.species not in self.species:
            raise ValueError(f"unknown species: {look.species}")
        if look.color not in self.colors:
            raise ValueError(f"unknown color: {look.color}")

        sp = look.species
        anchors = self.species[sp]["anchors"]
        img = Image.new("RGBA", self.size, (*self.manifest["background"], 255))

        shadow = Image.new("RGBA", self.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse((150, 462, 362, 500), fill=(0, 0, 0, 30))
        img.alpha_composite(shadow)

        img.alpha_composite(self._tinted_body(sp, look.color))
        img.alpha_composite(self._load(f"species/{sp}/extras.png"))

        for trait in sorted(look.traits):
            img.alpha_composite(self._layer(f"traits/{trait}", sp, anchors[self.traits[trait]["anchor"]]))

        img.alpha_composite(self._load(f"species/{sp}/lines.png"))
        img.alpha_composite(self._layer(f"expressions/{look.mood}", sp, anchors["face"]))

        slots = self.manifest["slot_order"]
        for item in sorted(look.items, key=lambda i: slots.index(self.item_slot(i))):
            img.alpha_composite(self._layer(f"items/{item}", sp, anchors[self.item_slot(item)]))

        return img.convert("RGB")

    def _tinted_body(self, sp: str, color: str) -> Image.Image:
        return _tint(str(self.assets / f"species/{sp}/body.png"), tuple(self.colors[color]["rgb"]))

    def _load(self, rel: str) -> Image.Image:
        return _open(str(self.assets / rel))

    def _layer(self, folder: str, sp: str, anchor: list[int]) -> Image.Image:
        own = self.assets / folder / f"{sp}.png"
        if own.exists():
            return _open(str(own))
        part = _open(str(self.assets / folder / "default.png"))
        full = Image.new("RGBA", self.size, (0, 0, 0, 0))
        full.alpha_composite(part, (anchor[0] - part.width // 2, anchor[1] - part.height // 2))
        return full


@lru_cache(maxsize=256)
def _open(path: str) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGBA")


@lru_cache(maxsize=64)
def _tint(path: str, rgb: tuple[int, int, int]) -> Image.Image:
    base = _open(path)
    color = Image.new("RGB", base.size, rgb)
    out = ImageChops.multiply(base.convert("RGB"), color).convert("RGBA")
    out.putalpha(base.split()[3])
    return out
