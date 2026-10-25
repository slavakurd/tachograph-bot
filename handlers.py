# -*- coding: utf-8 -*-
"""Обробники команд і кнопок / Command and button handlers."""

import time

from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
import db
import rules
import views
from texts import BUTTON_ACTIONS, LANGS, fmt_time, lang_from_code, t

MAX_BACKDATE_MIN = 12 * 60


def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    rows = [
        [t(lang, "btn_drive"), t(lang, "btn_rest")],
        [t(lang, "btn_work"), t(lang, "btn_status")],
        [t(lang, "btn_history"), t(lang, "btn_help")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def ensure_driver(update: Update) -> dict:
    """Повертає водія, за потреби реєструє (мова — з налаштувань Telegram)."""
    chat_id = update.effective_chat.id
    driver = db.get_driver(chat_id)
    if driver is None:
        user = update.effective_user
        db.register_driver(chat_id, user.first_name or "", lang_from_code(user.language_code))
        driver = db.get_driver(chat_id)
    return driver


def event_time(update: Update) -> int:
    """Час натискання (а не обробки) — важливо, якщо бот перезапускався."""
    msg = update.effective_message
    now = int(time.time())
    return min(now, int(msg.date.timestamp())) if msg and msg.date else now


def parse_minutes(args):
    """'/stop 10' -> 10. None — аргументу немає, -1 — некоректний."""
    if not args:
        return None
    try:
        minutes = int(args[0])
    except ValueError:
        return -1
    return minutes if 0 <= minutes <= MAX_BACKDATE_MIN else -1


async def reply(update: Update, text: str, lang: str):
    await update.effective_message.reply_text(text, reply_markup=main_keyboard(lang))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    name = update.effective_user.first_name or ""
    if name and name != driver["name"]:
        db.update_driver(driver["chat_id"], name=name)
    await reply(update, t(driver["lang"], "welcome", name=name, tz=views.driver_zone_name(driver)), driver["lang"])


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    await reply(update, t(driver["lang"], "help", tz=views.driver_zone_name(driver)), driver["lang"])


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    if context.args and context.args[0].lower() in LANGS:
        new_lang = context.args[0].lower()
    else:
        new_lang = "en" if driver["lang"] == "uk" else "uk"
    db.update_driver(driver["chat_id"], lang=new_lang)
    await reply(update, t(new_lang, "lang_set"), new_lang)


async def cmd_tz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    lang = driver["lang"]
    now = int(time.time())
    if not context.args:
        name = views.driver_zone_name(driver)
        await reply(update, t(lang, "tz_current", tz=name, time=fmt_time(now, config.get_zone(name))), lang)
        return
    name = context.args[0].strip()
    if not config.is_valid_zone(name):
        await reply(update, t(lang, "tz_bad"), lang)
        return
    db.update_driver(driver["chat_id"], tz=name)
    await reply(update, t(lang, "tz_set", tz=name, time=fmt_time(now, config.get_zone(name))), lang)


async def switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    driver = ensure_driver(update)
    chat_id, lang = driver["chat_id"], driver["lang"]
    tz = views.driver_zone(driver)
    now = int(time.time())
    at = event_time(update)

    minutes = parse_minutes(context.args)
    if minutes == -1:
        await reply(update, t(lang, "bad_minutes"), lang)
        return
    if minutes:
        at = now - minutes * 60

    if driver["state"] == kind:
        await reply(update, t(lang, "already", time=fmt_time(driver["session_start"], tz, now)), lang)
        return

    current = db.current_mode(driver)
    floor = max(filter(None, [current[1] if current else None, db.last_history_end(chat_id)]), default=None)
    if floor and at < floor:
        if minutes:
            await reply(update, t(lang, "too_early", time=fmt_time(floor, tz, now)), lang)
            return
        at = floor  # годинник Telegram трохи відстає — не страшно

    before = db.load_summary(driver, at)
    db.switch_mode(chat_id, kind, at)
    driver = db.get_driver(chat_id)
    after = db.load_summary(driver, now)
    await reply(update, views.mode_started_text(kind, before, after, driver, at, now), lang)


async def cmd_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await switch_mode(update, context, rules.DRIVE)


async def cmd_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await switch_mode(update, context, rules.WORK)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await switch_mode(update, context, rules.REST)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    now = int(time.time())
    s = db.load_summary(driver, now)
    await reply(update, views.status_text(s, driver, now), driver["lang"])


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = ensure_driver(update)
    now = int(time.time())
    periods = db.load_periods(driver["chat_id"], now - config.HISTORY_DAYS * rules.DAY)
    s = db.load_summary(driver, now)
    await reply(update, views.history_text(periods, s, driver, now), driver["lang"])


ACTIONS = {
    "drive": cmd_drive,
    "work": cmd_work,
    "rest": cmd_stop,
    "status": cmd_status,
    "history": cmd_history,
    "help": cmd_help,
}


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки клавіатури; будь-який інший текст — довідка."""
    action = BUTTON_ACTIONS.get((update.effective_message.text or "").strip())
    context.args = []
    await ACTIONS.get(action, cmd_help)(update, context)


def bot_commands(lang: str):
    """Список команд для меню Telegram."""
    names = [
        ("drive", "cmd_drive"), ("work", "cmd_work"), ("stop", "cmd_stop"),
        ("status", "cmd_status"), ("history", "cmd_history"),
        ("tz", "cmd_tz"), ("lang", "cmd_lang"), ("help", "cmd_help"),
    ]
    return [BotCommand(cmd, t(lang, key)) for cmd, key in names]

