# -*- coding: utf-8 -*-
"""Сценарії «кнопка -> база -> відповідь -> нагадування» без справжнього Telegram."""
import asyncio
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
import handlers  # noqa: E402
import jobs  # noqa: E402
import rules  # noqa: E402
import texts  # noqa: E402

CHAT = 1001
T0 = int(datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc).timestamp())


class FakeMessage:
    def __init__(self, text, ts):
        self.text = text
        self.date = datetime.fromtimestamp(ts, timezone.utc)
        self.replies = []

    async def reply_text(self, text, reply_markup=None):
        self.replies.append(text)


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, disable_notification=False):
        self.sent.append((chat_id, text, disable_notification))


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.init(os.path.join(self.tmp.name, "test.db"))
        self.now = T0
        self.clock = mock.patch("time.time", side_effect=lambda: self.now)
        self.clock.start()
        self.bot = FakeBot()

    def tearDown(self):
        self.clock.stop()
        self.tmp.cleanup()

    def send(self, text, args=None, callback=None, language_code="uk"):
        msg = FakeMessage(text, self.now)
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=CHAT),
            effective_user=SimpleNamespace(first_name="Іван", language_code=language_code),
            effective_message=msg,
        )
        context = SimpleNamespace(args=args or [], bot=self.bot)
        asyncio.run((callback or handlers.on_text)(update, context))
        return "\n".join(msg.replies)

    def tick(self, minutes):
        self.now += minutes * 60
        asyncio.run(jobs.check_timers(SimpleNamespace(bot=self.bot)))

    def test_keyboard_buttons_switch_modes(self):
        self.send("/start", callback=handlers.cmd_start)
        reply = self.send(texts.t("uk", "btn_drive"))
        self.assertIn("🚛 Водіння з", reply)
        self.assertEqual(db.get_driver(CHAT)["state"], rules.DRIVE)

        self.now += 60 * 60
        reply = self.send(texts.t("uk", "btn_rest"))
        self.assertIn("Відпочинок з", reply)
        self.assertIn("45 хв", reply)
        self.assertEqual(db.get_driver(CHAT)["state"], rules.REST)

        self.now += 10 * 60
        reply = self.send(texts.t("uk", "btn_work"))
        self.assertIn("Інша робота", reply)
        self.assertEqual([p.kind for p in db.load_periods(CHAT, 0)], [rules.DRIVE, rules.REST])

    def test_language_from_telegram_settings(self):
        self.send("/start", callback=handlers.cmd_start, language_code="en")
        self.assertEqual(db.get_driver(CHAT)["lang"], "en")

    def test_short_stop_does_not_reset_and_alerts_fire_once(self):
        self.send("/drive", callback=handlers.cmd_drive)
        self.tick(4 * 60)
        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("перерви", self.bot.sent[0][1])

        self.send("/stop", callback=handlers.cmd_stop)
        self.now += 10 * 60
        reply = self.send("/drive", callback=handlers.cmd_drive)
        self.assertIn("Перерву не завершено", reply)

        self.tick(1)
        self.assertEqual(len(self.bot.sent), 1)  # «скоро перерва» вже було
        self.tick(30)
        self.assertEqual(len(self.bot.sent), 2)
        self.assertIn("ЧАС ЗУПИНИТИСЬ", self.bot.sent[1][1])
        self.tick(1)
        self.assertEqual(len(self.bot.sent), 2)

    def test_break_done_alert(self):
        self.send("/drive", callback=handlers.cmd_drive)
        self.now += 3 * 3600
        self.send("/stop", callback=handlers.cmd_stop)
        self.tick(44)
        self.assertEqual(self.bot.sent, [])
        self.tick(1)
        self.assertEqual(len(self.bot.sent), 1)
        self.assertIn("перерву виконано", self.bot.sent[0][1])

    def test_backdated_switch(self):
        self.send("/drive", callback=handlers.cmd_drive)
        self.now += 3600
        self.send("/stop 15", args=["15"], callback=handlers.cmd_stop)
        driver = db.get_driver(CHAT)
        self.assertEqual(driver["session_start"], self.now - 15 * 60)

        reply = self.send("/drive 500", args=["500"], callback=handlers.cmd_drive)
        self.assertIn("Не можна раніше", reply)
        reply = self.send("/drive x", args=["x"], callback=handlers.cmd_drive)
        self.assertIn("Приклад", reply)

    def test_status_and_history_render(self):
        self.assertIn("не вибрано", self.send("/status", callback=handlers.cmd_status))
        self.send("/drive", callback=handlers.cmd_drive)
        self.now += 2 * 3600
        status = self.send("/status", callback=handlers.cmd_status)
        self.assertIn("Без перерви: 2 год з 4 год 30 хв", status)
        self.assertIn("Можна їхати ще: 2 год 30 хв", status)
        self.send("/stop", callback=handlers.cmd_stop)
        self.now += 20 * 60
        status = self.send("/status", callback=handlers.cmd_status)
        self.assertIn("До завершення перерви (45 хв) залишилось 25 хв", status)
        history = self.send("/history", callback=handlers.cmd_history)
        self.assertIn("Водіння", history)
        self.assertIn("зараз", history)

    def test_timezone_command(self):
        self.send("/start", callback=handlers.cmd_start)
        self.assertIn("Невідомий", self.send("/tz", args=["Mars/Base"], callback=handlers.cmd_tz))
        self.send("/tz", args=["Europe/Warsaw"], callback=handlers.cmd_tz)
        self.assertEqual(db.get_driver(CHAT)["tz"], "Europe/Warsaw")

    def test_unknown_text_shows_help(self):
        self.assertIn("/drive", self.send("привіт"))


class TextsTest(unittest.TestCase):
    def test_languages_have_same_keys(self):
        self.assertEqual(set(texts.TEXTS["uk"]), set(texts.TEXTS["en"]))

    def test_lang_from_code(self):
        self.assertEqual(texts.lang_from_code("uk"), "uk")
        self.assertEqual(texts.lang_from_code("en-GB"), "en")
        self.assertEqual(texts.lang_from_code(None), "uk")

    def test_fmt_duration(self):
        self.assertEqual(texts.fmt_duration("uk", 4 * 3600 + 30 * 60), "4 год 30 хв")
        self.assertEqual(texts.fmt_duration("en", 45 * 60), "45m")


class AlertTextsTest(unittest.TestCase):
    ALERT_IDS = [
        "warn_break_soon", "warn_break_now",
        "warn_daily_soon", "warn_daily_extended", "warn_daily_ext_soon", "warn_daily_over",
        "warn_weekly_soon", "warn_weekly_over",
        "warn_shift_soon", "warn_shift_over",
        "warn_weekly_rest_soon", "warn_weekly_rest_over",
        "rest_break_done", "rest_daily_done",
    ]

    def test_every_alert_renders_in_both_languages(self):
        import views

        s = rules.summarize([], T0 + 3600, (rules.DRIVE, T0))
        for text_id in self.ALERT_IDS:
            alert = rules.Alert(text_id=text_id, key=f"{text_id}:0", covers=(), at=T0 + 7200)
            for lang in texts.LANGS:
                driver = {"chat_id": 1, "name": "A", "lang": lang, "tz": "Europe/Kyiv"}
                self.assertTrue(views.alert_text(alert, s, driver, T0 + 3600))

    def test_rules_only_emit_known_alerts(self):
        import inspect

        emitted = set(re.findall(r'"((?:warn|rest)_[a-z_]+)"', inspect.getsource(rules.due_alerts)))
        self.assertEqual(emitted, set(self.ALERT_IDS))


class MigrationTest(unittest.TestCase):
    def test_old_schema_is_migrated(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.db")
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE drivers (chat_id INTEGER PRIMARY KEY, name TEXT, lang TEXT DEFAULT 'uk', "
                "state TEXT DEFAULT 'idle', session_start INTEGER, daily_drive_min INTEGER DEFAULT 0, "
                "daily_date TEXT, warned_30 INTEGER DEFAULT 0, warned_stop INTEGER DEFAULT 0)"
            )
            conn.execute("INSERT INTO drivers (chat_id, name, state, session_start) VALUES (1, 'A', 'driving', 100)")
            conn.commit()
            conn.close()

            db.init(path)
            driver = db.get_driver(1)
            self.assertEqual(driver["state"], rules.DRIVE)
            self.assertIsNone(driver["tz"])


if __name__ == "__main__":
    unittest.main()
