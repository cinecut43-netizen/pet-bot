import io
import itertools
from pathlib import Path

import pytest
from PIL import Image

from bot.render import Look, Renderer

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@pytest.fixture
def renderer(tmp_path):
    return Renderer(ASSETS, tmp_path)


def test_every_combination_renders(renderer):
    """Каждая вещь, черта и выражение собираются на каждом виде."""
    for sp, mood, trait, item in itertools.product(
        renderer.species, renderer.manifest["moods"], renderer.traits, renderer.items
    ):
        img = renderer.compose(Look(sp, "ginger", mood, (trait,), (item,)))
        assert img.size == tuple(renderer.manifest["canvas"])


def test_cache_key_ignores_order(renderer):
    a = Look("cat", "gray", "ok", ("star", "freckles"), ("scarf", "beanie"))
    b = Look("cat", "gray", "ok", ("freckles", "star"), ("beanie", "scarf"))
    assert renderer.cache_key(a) == renderer.cache_key(b)
    assert renderer.cache_key(a) != renderer.cache_key(Look("cat", "gray", "happy"))


def test_render_png_is_cached_on_disk(renderer, tmp_path):
    look = Look("fox", "mint", "happy", (), ("glasses",))
    data = renderer.render_png(look)
    assert Image.open(io.BytesIO(data)).format == "PNG"
    assert (tmp_path / f"{renderer.cache_key(look)}.png").read_bytes() == data


def test_grid(renderer):
    looks = [Look(sp, "cream", "happy") for sp in renderer.species]
    img = Image.open(io.BytesIO(renderer.grid_png(looks)))
    assert img.size == (768, 256)


def test_unknown_species_rejected(renderer):
    with pytest.raises(ValueError):
        renderer.compose(Look("dragon", "gray", "ok"))
