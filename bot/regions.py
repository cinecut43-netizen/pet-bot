"""Часовые пояса России: напоминание должно приходить вечером по местному времени,
а не по Москве (от Калининграда до Камчатки разница 10 часов)."""

from __future__ import annotations

DEFAULT_TZ = "Europe/Moscow"

# ключ (короткий, для callback_data) → (IANA-зона, подпись на кнопке)
TIMEZONES: dict[str, tuple[str, str]] = {
    "kgd": ("Europe/Kaliningrad", "Калининград (МСК−1)"),
    "msk": ("Europe/Moscow", "Москва (МСК)"),
    "sam": ("Europe/Samara", "Самара (МСК+1)"),
    "ekb": ("Asia/Yekaterinburg", "Екатеринбург (МСК+2)"),
    "oms": ("Asia/Omsk", "Омск (МСК+3)"),
    "krs": ("Asia/Krasnoyarsk", "Красноярск, Новосибирск (МСК+4)"),
    "irk": ("Asia/Irkutsk", "Иркутск (МСК+5)"),
    "yak": ("Asia/Yakutsk", "Якутск, Чита (МСК+6)"),
    "vla": ("Asia/Vladivostok", "Владивосток, Хабаровск (МСК+7)"),
    "mag": ("Asia/Magadan", "Магадан, Сахалин (МСК+8)"),
    "kam": ("Asia/Kamchatka", "Камчатка, Чукотка (МСК+9)"),
}

TZ_LABELS = {tz: label for tz, label in TIMEZONES.values()}


def tz_label(tz: str) -> str:
    return TZ_LABELS.get(tz, tz)
