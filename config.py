# -*- coding: utf-8 -*-
"""Налаштування з змінних середовища / Config from environment variables."""

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# На Railway підключіть Volume (наприклад, у /data) і задайте DB_PATH=/data/tachograph.db,
# інакше база зникає після кожного деплою.
DB_PATH = os.environ.get("DB_PATH", "tachograph.db")

# Часовий пояс за замовчуванням для нових водіїв (кожен може змінити через /tz).
DEFAULT_TZ = os.environ.get("DEFAULT_TZ") or os.environ.get("TZ") or "Europe/Kyiv"

CHECK_INTERVAL_SEC = int(os.environ.get("CHECK_INTERVAL_SEC", "60"))

# Скільки днів історії враховувати в розрахунках (два тижні + запас).
HISTORY_DAYS = 28


def get_zone(name):
    """ZoneInfo за назвою; некоректна назва -> UTC."""
    if name:
        try:
            return ZoneInfo(name.lstrip(":"))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo("UTC")


def is_valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False
