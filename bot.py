# -*- coding: utf-8 -*-
"""
Tachograph Reminder Bot / Бот-нагадувач режиму праці та відпочинку водія
========================================================================

Водій натискає кнопку щоразу, коли змінює режим (водіння / інша робота /
відпочинок), а бот рахує ліміти за Регламентом (ЄС) 561/2006 / AETR і сам
надсилає попередження. Розрахунок спрощений, для довідки, і НЕ є юридичною
консультацією — водій завжди керується офіційними правилами та тахографом.

Структура:
    bot.py       — запуск, реєстрація обробників і фонових задач
    config.py    — налаштування зі змінних середовища
    rules.py     — правила 561/2006 (без Telegram, покрито тестами)
    db.py        — SQLite
    texts.py     — тексти uk/en, форматування часу
    views.py     — тексти повідомлень зі статусом / історією / попередженнями
    handlers.py  — команди та кнопки
    jobs.py      — фонова перевірка таймерів

ЗАПУСК:
    pip install -r requirements.txt
    export BOT_TOKEN="ваш_токен_від_BotFather"
    python3 bot.py
"""

import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import config
import db
import handlers
import jobs
import rules

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx на рівні INFO пише в лог URL кожного запиту разом з токеном бота
logging.getLogger("httpx").setLevel(logging.WARNING)
# APScheduler інакше пише кожен запуск перевірки (раз на хвилину)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    try:
        await app.bot.set_my_commands(handlers.bot_commands("uk"))
        await app.bot.set_my_commands(handlers.bot_commands("en"), language_code="en")
    except TelegramError as e:
        # Меню команд — не критично, бот має працювати і без нього
        logger.warning("Failed to set bot commands: %s", e)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled error while processing %s", update, exc_info=context.error)


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN не задано. Встановіть змінну середовища BOT_TOKEN.")

    db.init()

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # Лише нові повідомлення: редагування старої команди не повинно перемикати режим
    new_msg = filters.UpdateType.MESSAGE
    commands = {
        "start": handlers.cmd_start,
        "help": handlers.cmd_help,
        "lang": handlers.cmd_lang,
        "tz": handlers.cmd_tz,
        "drive": handlers.cmd_drive,
        "start_drive": handlers.cmd_drive,  # стара назва команди
        "work": handlers.cmd_work,
        "stop": handlers.cmd_stop,
        "rest": handlers.cmd_stop,
        "status": handlers.cmd_status,
        "history": handlers.cmd_history,
    }
    for name, callback in commands.items():
        app.add_handler(CommandHandler(name, callback, filters=new_msg))
    app.add_handler(MessageHandler(new_msg & filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_error_handler(on_error)

    app.job_queue.run_repeating(jobs.check_timers, interval=config.CHECK_INTERVAL_SEC, first=10)
    app.job_queue.run_repeating(jobs.purge_old_alerts, interval=rules.DAY, first=60)

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
