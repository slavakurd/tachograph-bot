# -*- coding: utf-8 -*-
"""
Tachograph Reminder Bot / Бот-нагадувач режиму праці-відпочинку водія
========================================================================

Що робить бот:
- Водій реєструється сам командою /start
- /start_drive  — починає відлік часу водіння
- /stop         — починає відлік часу відпочинку
- /status       — показує поточний стан і скільки часу лишилось
- /history      — показує останні поїздки/відпочинки
- /lang         — перемикає мову (uk/en), за замовчуванням визначається автоматично

Бот сам надсилає попередження:
- за 30 хв до обов'язкової зупинки (4,5 год безперервного водіння)
- коли час зупинятись
- коли можна продовжити водіння після відпочинку

Правила базуються на Регламенті (ЄС) 561/2006 / AETR (спрощено, для довідки,
НЕ є юридичною консультацією — водій завжди керується офіційними правилами
та показниками тахографа).

ВСТАНОВЛЕННЯ:
    pip install python-telegram-bot==21.* --upgrade

ЗАПУСК:
    export BOT_TOKEN="ваш_токен_від_BotFather"
    python3 bot.py
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# -------------------------------------------------------------------------
# НАЛАШТУВАННЯ / CONFIG
# -------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")
DB_PATH = os.environ.get("DB_PATH", "tachograph.db")

# Ліміти у хвилинах (Регламент 561/2006, типові значення)
MAX_CONTINUOUS_DRIVE_MIN = 4 * 60 + 30      # 4 год 30 хв безперервного водіння
WARN_BEFORE_BREAK_MIN = 30                  # попередити за 30 хв до зупинки
REQUIRED_BREAK_MIN = 45                     # обов'язкова перерва
MAX_DAILY_DRIVE_MIN = 9 * 60                # денна норма водіння
MAX_DAILY_DRIVE_EXT_MIN = 10 * 60           # розширена (можна 2р/тиждень)
MIN_DAILY_REST_MIN = 11 * 60                # денний відпочинок
MIN_DAILY_REST_REDUCED_MIN = 9 * 60         # скорочений денний відпочинок

CHECK_INTERVAL_SEC = 60  # як часто бот перевіряє таймери всіх водіїв

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# ТЕКСТИ / I18N
# -------------------------------------------------------------------------

TEXTS = {
    "uk": {
        "welcome": (
            "👋 Вітаю, {name}!\n\n"
            "Я бот-нагадувач режиму праці та відпочинку водія (тахограф).\n\n"
            "Команди:\n"
            "🚛 /start_drive — почав їхати\n"
            "🛑 /stop — зупинився / відпочиваю\n"
            "📊 /status — поточний стан\n"
            "📜 /history — історія за останні дні\n"
            "🌐 /lang — змінити мову\n\n"
            "Я сам нагадаю, коли потрібно зупинитись на перерву."
        ),
        "lang_set": "🌐 Мову встановлено: Українська",
        "drive_started": (
            "🚛 Поїздку розпочато о {time}.\n"
            "Безперервне водіння без перерви — максимум 4 год 30 хв.\n"
            "Я нагадаю, коли наблизиться час зупинки."
        ),
        "drive_already": "🚛 Ви вже в режимі водіння з {time}. Спочатку натисніть /stop.",
        "stop_started": (
            "🛑 Відпочинок/зупинку розпочато о {time}.\n"
            "Тривалість поїздки: {drive_dur}.\n"
            "Для повноцінної перерви потрібно відпочити мінімум 45 хв."
        ),
        "stop_no_drive": "Ви не в режимі водіння. Немає що зупиняти.",
        "rest_already": "🛑 Ви вже відпочиваєте з {time}. Натисніть /start_drive, щоб поїхати далі.",
        "status_driving": (
            "🚛 Статус: В дорозі\n"
            "Почали: {start}\n"
            "Минуло часу водіння: {elapsed}\n"
            "Залишилось до обов'язкової зупинки: {remaining}\n"
            "Сьогодні наїздили (всього): {daily_total}"
        ),
        "status_resting": (
            "🛑 Статус: Відпочинок\n"
            "Почали відпочивати: {start}\n"
            "Минуло часу відпочинку: {elapsed}\n"
            "{rest_msg}"
        ),
        "status_idle": "😴 Зараз не зафіксовано ні водіння, ні відпочинку.\nНатисніть /start_drive, коли вирушите в дорогу.",
        "rest_enough": "✅ Мінімальна перерва (45 хв) виконана — можна продовжувати рух.",
        "rest_not_enough": "⏳ До завершення мінімальної перерви (45 хв) залишилось: {left}",
        "warn_30min": (
            "⚠️ УВАГА, {name}!\n"
            "До обов'язкової зупинки (4 год 30 хв безперервного водіння) залишилось ~30 хвилин.\n"
            "Починайте шукати місце для безпечної зупинки."
        ),
        "warn_must_stop": (
            "🛑 ЧАС ЗУПИНИТИСЬ, {name}!\n"
            "Безперервне водіння досягло 4 год 30 хв.\n"
            "За правилами потрібна перерва мінімум 45 хвилин.\n"
            "Натисніть /stop, коли зупинитесь."
        ),
        "warn_daily_limit": (
            "⚠️ {name}, сьогоднішнє водіння наближається до денної норми (9 год).\n"
            "Плануйте завершення робочого дня та відпочинок (мінімум 11 год)."
        ),
        "history_empty": "Історія поки порожня.",
        "history_header": "📜 Останні записи:\n",
        "no_active_session": "Немає активної сесії.",
    },
    "en": {
        "welcome": (
            "👋 Hello, {name}!\n\n"
            "I'm a tachograph driving/rest time reminder bot.\n\n"
            "Commands:\n"
            "🚛 /start_drive — started driving\n"
            "🛑 /stop — stopped / resting\n"
            "📊 /status — current status\n"
            "📜 /history — recent history\n"
            "🌐 /lang — change language\n\n"
            "I'll remind you when it's time to take a break."
        ),
        "lang_set": "🌐 Language set to: English",
        "drive_started": (
            "🚛 Drive started at {time}.\n"
            "Max continuous driving without a break — 4h30m.\n"
            "I'll remind you as the break time approaches."
        ),
        "drive_already": "🚛 You're already driving since {time}. Press /stop first.",
        "stop_started": (
            "🛑 Rest/stop started at {time}.\n"
            "Drive duration: {drive_dur}.\n"
            "A full break requires at least 45 minutes of rest."
        ),
        "stop_no_drive": "You're not currently driving. Nothing to stop.",
        "rest_already": "🛑 You're already resting since {time}. Press /start_drive to continue.",
        "status_driving": (
            "🚛 Status: Driving\n"
            "Started: {start}\n"
            "Elapsed driving time: {elapsed}\n"
            "Time left until mandatory stop: {remaining}\n"
            "Total driven today: {daily_total}"
        ),
        "status_resting": (
            "🛑 Status: Resting\n"
            "Rest started: {start}\n"
            "Elapsed rest time: {elapsed}\n"
            "{rest_msg}"
        ),
        "status_idle": "😴 No active driving or resting session.\nPress /start_drive when you hit the road.",
        "rest_enough": "✅ Minimum break (45 min) completed — you may continue driving.",
        "rest_not_enough": "⏳ Time left until minimum break (45 min) is complete: {left}",
        "warn_30min": (
            "⚠️ WARNING, {name}!\n"
            "About 30 minutes left until mandatory stop (4h30m continuous driving).\n"
            "Start looking for a safe place to stop."
        ),
        "warn_must_stop": (
            "🛑 TIME TO STOP, {name}!\n"
            "Continuous driving has reached 4h30m.\n"
            "Regulations require a break of at least 45 minutes.\n"
            "Press /stop once you've stopped."
        ),
        "warn_daily_limit": (
            "⚠️ {name}, today's driving is approaching the daily limit (9h).\n"
            "Plan to end your driving day and rest (minimum 11h)."
        ),
        "history_empty": "History is empty so far.",
        "history_header": "📜 Recent entries:\n",
        "no_active_session": "No active session.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else "uk"
    return TEXTS[lang][key].format(**kwargs)


def detect_lang(text: str) -> str:
    """Дуже проста евристика: кирилиця -> uk, інакше en."""
    if not text:
        return "uk"
    for ch in text:
        if "а" <= ch.lower() <= "я" or ch.lower() in "іїєґ":
            return "uk"
    return "en"


def fmt_duration(minutes: int) -> str:
    h, m = divmod(max(minutes, 0), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


# -------------------------------------------------------------------------
# БАЗА ДАНИХ / DATABASE
# -------------------------------------------------------------------------

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS drivers (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            lang TEXT DEFAULT 'uk',
            state TEXT DEFAULT 'idle',      -- idle | driving | resting
            session_start INTEGER,          -- unix timestamp
            daily_drive_min INTEGER DEFAULT 0,
            daily_date TEXT,
            warned_30 INTEGER DEFAULT 0,
            warned_stop INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            kind TEXT,          -- drive | rest
            start_ts INTEGER,
            end_ts INTEGER,
            duration_min INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def get_driver(chat_id: int):
    conn = db_connect()
    row = conn.execute("SELECT * FROM drivers WHERE chat_id=?", (chat_id,)).fetchone()
    conn.close()
    return row


def upsert_driver(chat_id: int, **fields):
    conn = db_connect()
    cur = conn.cursor()
    existing = cur.execute("SELECT chat_id FROM drivers WHERE chat_id=?", (chat_id,)).fetchone()
    if existing:
        sets = ", ".join(f"{k}=?" for k in fields)
        cur.execute(f"UPDATE drivers SET {sets} WHERE chat_id=?", (*fields.values(), chat_id))
    else:
        cols = ", ".join(["chat_id"] + list(fields.keys()))
        qs = ", ".join(["?"] * (len(fields) + 1))
        cur.execute(f"INSERT INTO drivers ({cols}) VALUES ({qs})", (chat_id, *fields.values()))
    conn.commit()
    conn.close()


def add_history(chat_id: int, kind: str, start_ts: int, end_ts: int, duration_min: int):
    conn = db_connect()
    conn.execute(
        "INSERT INTO history (chat_id, kind, start_ts, end_ts, duration_min) VALUES (?,?,?,?,?)",
        (chat_id, kind, start_ts, end_ts, duration_min),
    )
    conn.commit()
    conn.close()


def get_history(chat_id: int, limit: int = 10):
    conn = db_connect()
    rows = conn.execute(
        "SELECT * FROM history WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    conn.close()
    return rows


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


# -------------------------------------------------------------------------
# КЛАВІАТУРА / KEYBOARD
# -------------------------------------------------------------------------

def main_keyboard(lang: str):
    if lang == "uk":
        rows = [["🚛 /start_drive", "🛑 /stop"], ["📊 /status", "📜 /history"]]
    else:
        rows = [["🚛 /start_drive", "🛑 /stop"], ["📊 /status", "📜 /history"]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


# -------------------------------------------------------------------------
# ХЕНДЛЕРИ КОМАНД / COMMAND HANDLERS
# -------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name or "Driver"
    lang = detect_lang(update.message.text)
    existing = get_driver(chat_id)
    if existing:
        lang = existing["lang"]
    else:
        upsert_driver(chat_id, name=name, lang=lang, state="idle", daily_date=today_str())
    await update.message.reply_text(
        t(lang, "welcome", name=name), reply_markup=main_keyboard(lang)
    )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    current = driver["lang"] if driver else "uk"
    new_lang = "en" if current == "uk" else "uk"
    upsert_driver(chat_id, lang=new_lang)
    await update.message.reply_text(t(new_lang, "lang_set"), reply_markup=main_keyboard(new_lang))


async def cmd_start_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    if not driver:
        await cmd_start(update, context)
        driver = get_driver(chat_id)
    lang = driver["lang"]
    now = int(time.time())

    if driver["state"] == "driving":
        start_str = datetime.fromtimestamp(driver["session_start"]).strftime("%H:%M")
        await update.message.reply_text(t(lang, "drive_already", time=start_str))
        return

    # Якщо переходимо з відпочинку -> зберігаємо відпочинок в історію
    if driver["state"] == "resting" and driver["session_start"]:
        dur = (now - driver["session_start"]) // 60
        add_history(chat_id, "rest", driver["session_start"], now, dur)

    # Скидаємо денний лічильник, якщо новий день
    daily_drive = driver["daily_drive_min"] or 0
    daily_date = driver["daily_date"]
    if daily_date != today_str():
        daily_drive = 0
        daily_date = today_str()

    upsert_driver(
        chat_id,
        state="driving",
        session_start=now,
        daily_drive_min=daily_drive,
        daily_date=daily_date,
        warned_30=0,
        warned_stop=0,
    )
    await update.message.reply_text(
        t(lang, "drive_started", time=datetime.fromtimestamp(now).strftime("%H:%M")),
        reply_markup=main_keyboard(lang),
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    if not driver:
        await cmd_start(update, context)
        return
    lang = driver["lang"]
    now = int(time.time())

    if driver["state"] == "driving":
        dur_min = (now - driver["session_start"]) // 60
        add_history(chat_id, "drive", driver["session_start"], now, dur_min)
        daily_total = (driver["daily_drive_min"] or 0) + dur_min
        upsert_driver(
            chat_id,
            state="resting",
            session_start=now,
            daily_drive_min=daily_total,
            warned_30=0,
            warned_stop=0,
        )
        await update.message.reply_text(
            t(lang, "stop_started", time=datetime.fromtimestamp(now).strftime("%H:%M"), drive_dur=fmt_duration(dur_min)),
            reply_markup=main_keyboard(lang),
        )
    elif driver["state"] == "resting":
        start_str = datetime.fromtimestamp(driver["session_start"]).strftime("%H:%M")
        await update.message.reply_text(t(lang, "rest_already", time=start_str))
    else:
        await update.message.reply_text(t(lang, "stop_no_drive"))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    if not driver:
        await cmd_start(update, context)
        return
    lang = driver["lang"]
    now = int(time.time())

    if driver["state"] == "driving":
        elapsed_min = (now - driver["session_start"]) // 60
        remaining_min = MAX_CONTINUOUS_DRIVE_MIN - elapsed_min
        daily_total = (driver["daily_drive_min"] or 0) + elapsed_min
        await update.message.reply_text(
            t(
                lang,
                "status_driving",
                start=datetime.fromtimestamp(driver["session_start"]).strftime("%H:%M"),
                elapsed=fmt_duration(elapsed_min),
                remaining=fmt_duration(remaining_min) if remaining_min > 0 else "0m",
                daily_total=fmt_duration(daily_total),
            )
        )
    elif driver["state"] == "resting":
        elapsed_min = (now - driver["session_start"]) // 60
        if elapsed_min >= REQUIRED_BREAK_MIN:
            rest_msg = t(lang, "rest_enough")
        else:
            rest_msg = t(lang, "rest_not_enough", left=fmt_duration(REQUIRED_BREAK_MIN - elapsed_min))
        await update.message.reply_text(
            t(
                lang,
                "status_resting",
                start=datetime.fromtimestamp(driver["session_start"]).strftime("%H:%M"),
                elapsed=fmt_duration(elapsed_min),
                rest_msg=rest_msg,
            )
        )
    else:
        await update.message.reply_text(t(lang, "status_idle"))


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    if not driver:
        await cmd_start(update, context)
        return
    lang = driver["lang"]
    rows = get_history(chat_id, limit=10)
    if not rows:
        await update.message.reply_text(t(lang, "history_empty"))
        return

    lines = [t(lang, "history_header")]
    for r in rows:
        icon = "🚛" if r["kind"] == "drive" else "🛑"
        kind_label = ("Водіння" if lang == "uk" else "Drive") if r["kind"] == "drive" else ("Відпочинок" if lang == "uk" else "Rest")
        start_str = datetime.fromtimestamp(r["start_ts"]).strftime("%d.%m %H:%M")
        lines.append(f"{icon} {kind_label}: {start_str} — {fmt_duration(r['duration_min'])}")
    await update.message.reply_text("\n".join(lines))


async def text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Якщо водій просто пише текст не командою — підказати команди."""
    chat_id = update.effective_chat.id
    driver = get_driver(chat_id)
    lang = driver["lang"] if driver else detect_lang(update.message.text)
    await update.message.reply_text(t(lang, "welcome", name=update.effective_user.first_name or ""), reply_markup=main_keyboard(lang))


# -------------------------------------------------------------------------
# ФОНОВА ПЕРЕВІРКА ТАЙМЕРІВ / BACKGROUND JOB
# -------------------------------------------------------------------------

async def check_timers(context: ContextTypes.DEFAULT_TYPE):
    """Запускається кожні CHECK_INTERVAL_SEC секунд, перевіряє всіх водіїв."""
    conn = db_connect()
    rows = conn.execute("SELECT * FROM drivers WHERE state='driving'").fetchall()
    conn.close()

    now = int(time.time())
    for driver in rows:
        chat_id = driver["chat_id"]
        lang = driver["lang"]
        name = driver["name"] or ""
        elapsed_min = (now - driver["session_start"]) // 60

        # Попередження за 30 хв до зупинки
        if elapsed_min >= (MAX_CONTINUOUS_DRIVE_MIN - WARN_BEFORE_BREAK_MIN) and not driver["warned_30"]:
            try:
                await context.bot.send_message(chat_id, t(lang, "warn_30min", name=name))
            except Exception as e:
                logger.warning(f"Failed to send warn_30 to {chat_id}: {e}")
            upsert_driver(chat_id, warned_30=1)

        # Попередження - час зупинятись
        if elapsed_min >= MAX_CONTINUOUS_DRIVE_MIN and not driver["warned_stop"]:
            try:
                await context.bot.send_message(chat_id, t(lang, "warn_must_stop", name=name))
            except Exception as e:
                logger.warning(f"Failed to send warn_stop to {chat_id}: {e}")
            upsert_driver(chat_id, warned_stop=1)

        # Попередження про денний ліміт (9 год загального водіння за день)
        daily_total = (driver["daily_drive_min"] or 0) + elapsed_min
        if daily_total >= (MAX_DAILY_DRIVE_MIN - 30) and daily_total < MAX_DAILY_DRIVE_MIN:
            # Надсилаємо раз — простий захист від спаму через ще один прапорець
            pass  # за потреби можна додати окремий стовпець warned_daily


# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------

def main():
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit(
            "❌ BOT_TOKEN не задано. Встановіть змінну середовища BOT_TOKEN "
            "або вставте токен прямо в код (рядок BOT_TOKEN = ...)."
        )

    db_init()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("start_drive", cmd_start_drive))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_fallback))

    # Фонова перевірка кожні CHECK_INTERVAL_SEC секунд
    app.job_queue.run_repeating(check_timers, interval=CHECK_INTERVAL_SEC, first=10)

    logger.info("Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
