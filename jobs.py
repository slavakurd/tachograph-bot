# -*- coding: utf-8 -*-
"""Фонові перевірки / Background jobs."""

import logging
import time

from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes

import db
import rules
import views

logger = logging.getLogger(__name__)

# Відпочинки, довші за це, вже не потребують нагадувань (останнє — 11 год).
REST_CHECK_WINDOW = rules.DAILY_REST + rules.HOUR
SENT_ALERTS_TTL = 35 * rules.DAY

# Не будити водія вночі — ці повідомлення надсилаються без звуку.
SILENT_ALERTS = {"rest_daily_done"}


async def check_timers(context: ContextTypes.DEFAULT_TYPE):
    """Кожні CHECK_INTERVAL_SEC секунд перевіряє водіїв і надсилає попередження."""
    now = int(time.time())
    for driver in db.drivers_to_check(now - REST_CHECK_WINDOW):
        chat_id = driver["chat_id"]
        try:
            s = db.load_summary(driver, now)
            alerts = rules.due_alerts(s)
            if not alerts:
                continue
            sent = db.sent_alert_keys(chat_id)
            for alert in alerts:
                if alert.key in sent:
                    continue
                text = views.alert_text(alert, s, driver, now)
                try:
                    await context.bot.send_message(
                        chat_id, text, disable_notification=alert.text_id in SILENT_ALERTS
                    )
                except (Forbidden, BadRequest) as e:
                    # Водій заблокував бота / чат не існує — повтор не допоможе
                    logger.warning("Alert %s not delivered to %s: %s", alert.text_id, chat_id, e)
                except TelegramError as e:
                    # Мережа / ліміти Telegram — спробуємо на наступній перевірці
                    logger.warning("Alert %s to %s failed, will retry: %s", alert.text_id, chat_id, e)
                    continue
                db.mark_alerts_sent(chat_id, alert.covers, now)
        except Exception:
            logger.exception("check_timers failed for %s", chat_id)


async def purge_old_alerts(context: ContextTypes.DEFAULT_TYPE):
    db.purge_sent_alerts(int(time.time()) - SENT_ALERTS_TTL)
