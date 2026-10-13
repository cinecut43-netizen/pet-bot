from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    admin_ids: frozenset[int]
    assets_dir: Path
    cache_dir: Path
    privacy_contact: str        # контакт для вопросов о данных, показывается в /privacy
    telegram_proxy: str | None  # http(s)/socks5-прокси до api.telegram.org, если сервер его не видит
    telegram_api_url: str | None  # свой Local Bot API Server вместо api.telegram.org


def _load_dotenv(path: Path) -> None:
    """Минимальный разбор .env, чтобы не тянуть лишнюю зависимость."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> Config:
    _load_dotenv(BASE_DIR / ".env")
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        raise SystemExit("BOT_TOKEN не задан — скопируйте .env.example в .env и заполните")
    admins = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
    return Config(
        bot_token=token,
        database_url=os.environ.get("DATABASE_URL", "postgresql://pet:pet@localhost:5432/pet"),
        admin_ids=frozenset(admins),
        assets_dir=Path(os.environ.get("ASSETS_DIR", BASE_DIR / "assets")),
        cache_dir=Path(os.environ.get("CACHE_DIR", BASE_DIR / "cache")),
        privacy_contact=os.environ.get("PRIVACY_CONTACT", "").strip(),
        telegram_proxy=os.environ.get("TELEGRAM_PROXY", "").strip() or None,
        telegram_api_url=os.environ.get("TELEGRAM_API_URL", "").strip().rstrip("/") or None,
    )
