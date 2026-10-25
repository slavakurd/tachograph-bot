# -*- coding: utf-8 -*-
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import rules  # noqa: E402
from rules import DRIVE, HOUR, MIN, REST, WORK, Period  # noqa: E402

# Понеділок 19.10.2026 06:00 UTC
BASE = int(datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc).timestamp())


def build(steps, start=BASE):
    """[(kind, хвилини), ...] -> (завершені періоди, (kind, since) останнього, now).
    Останній крок вважається поточним (відкритим) режимом."""
    periods = []
    ts = start
    for kind, minutes in steps:
        periods.append(Period(kind, ts, ts + minutes * MIN))
        ts += minutes * MIN
    last = periods.pop()
    return periods, (last.kind, last.start), last.end


def summary(steps, start=BASE):
    history, current, now = build(steps, start)
    return rules.summarize(history, now, current)


def alert_ids(s):
    return [a.text_id for a in rules.due_alerts(s)]


class ContinuousDrivingTest(unittest.TestCase):
    def test_short_stop_does_not_reset_counter(self):
        s = summary([(DRIVE, 240), (REST, 10), (DRIVE, 20)])
        self.assertEqual(s.continuous_drive, 260 * MIN)
        self.assertEqual(s.continuous_left, 10 * MIN)

    def test_45_min_break_resets_counter(self):
        s = summary([(DRIVE, 240), (REST, 45), (DRIVE, 10)])
        self.assertEqual(s.continuous_drive, 10 * MIN)
        self.assertEqual(s.break_anchor, BASE + 285 * MIN)

    def test_split_break_15_then_30_resets(self):
        s = summary([(DRIVE, 120), (REST, 15), (DRIVE, 120), (REST, 30), (DRIVE, 5)])
        self.assertEqual(s.continuous_drive, 5 * MIN)

    def test_split_break_in_wrong_order_does_not_reset(self):
        s = summary([(DRIVE, 120), (REST, 30), (DRIVE, 120), (REST, 15), (DRIVE, 5)])
        self.assertEqual(s.continuous_drive, 245 * MIN)
        self.assertTrue(s.split_first_taken)

    def test_other_work_is_not_a_break(self):
        s = summary([(DRIVE, 240), (WORK, 60), (DRIVE, 10)])
        self.assertEqual(s.continuous_drive, 250 * MIN)

    def test_open_rest_break_target_and_needed(self):
        s = summary([(DRIVE, 200), (REST, 20)])
        self.assertEqual(s.rest_break_target, 45 * MIN)
        self.assertEqual(s.break_needed, 25 * MIN)
        self.assertEqual(s.continuous_drive, 200 * MIN)

        s = summary([(DRIVE, 100), (REST, 15), (DRIVE, 100), (REST, 10)])
        self.assertEqual(s.rest_break_target, 30 * MIN)
        self.assertEqual(s.break_needed, 20 * MIN)

    def test_open_rest_completes_break(self):
        s = summary([(DRIVE, 200), (REST, 50)])
        self.assertEqual(s.break_needed, 0)
        self.assertEqual(s.continuous_drive, 0)
        self.assertEqual(s.continuous_left, rules.MAX_CONTINUOUS_DRIVE)

    def test_just_switched_to_rest(self):
        history, _, now = build([(DRIVE, 200), (REST, 1)])
        s = rules.summarize(history, now, (REST, now))
        self.assertEqual(s.kind, REST)
        self.assertEqual(s.current_rest, 0)
        self.assertEqual(s.rest_break_target, 45 * MIN)

    def test_no_break_needed_without_driving(self):
        s = summary([(WORK, 60), (REST, 10)])
        self.assertEqual(s.rest_break_target, 0)
        self.assertEqual(s.break_needed, 0)


class DailyTest(unittest.TestCase):
    def test_daily_rest_starts_new_shift(self):
        s = summary([(DRIVE, 240), (REST, 45), (DRIVE, 240), (REST, 11 * 60), (DRIVE, 60)])
        self.assertEqual(s.shift_drive, 60 * MIN)
        self.assertEqual(s.shift_start, BASE + (240 + 45 + 240 + 660) * MIN)

    def test_gap_in_history_is_rest(self):
        history = [
            Period(DRIVE, BASE, BASE + 4 * HOUR),
            Period(DRIVE, BASE + 16 * HOUR, BASE + 17 * HOUR),
        ]
        s = rules.summarize(history, BASE + 17 * HOUR + 30 * MIN, (DRIVE, BASE + 17 * HOUR))
        self.assertEqual(s.shift_drive, 90 * MIN)
        self.assertEqual(s.continuous_drive, 90 * MIN)

    def test_rest_deadline(self):
        s = summary([(DRIVE, 60)])
        self.assertEqual(s.rest_deadline_regular, BASE + 13 * HOUR)
        self.assertEqual(s.rest_deadline, BASE + 15 * HOUR)  # скорочений відпочинок доступний

    def test_reduced_rests_counted_and_exhausted(self):
        steps = []
        for _ in range(3):
            steps += [(DRIVE, 240), (REST, 45), (DRIVE, 60), (REST, 9 * 60)]
        steps.append((DRIVE, 30))
        s = summary(steps)
        self.assertEqual(s.reduced_rests_used, 3)
        self.assertEqual(s.reduced_rests_left, 0)
        self.assertEqual(s.rest_deadline, s.shift_start + 13 * HOUR)

    def test_split_daily_rest_3_plus_9_is_not_reduced(self):
        s = summary([(DRIVE, 240), (REST, 3 * 60), (DRIVE, 240), (REST, 9 * 60), (DRIVE, 10)])
        self.assertEqual(s.reduced_rests_used, 0)

    def test_split_daily_rest_shifts_deadline(self):
        s = summary([(DRIVE, 240), (REST, 3 * 60), (DRIVE, 60)])
        self.assertTrue(s.shift_has_3h_rest)
        self.assertEqual(s.rest_deadline_regular, BASE + 15 * HOUR)

    def test_extended_days(self):
        day = [(DRIVE, 270), (REST, 45), (DRIVE, 270), (REST, 45), (DRIVE, 30), (REST, 11 * 60)]
        s = summary(day + day + [(DRIVE, 60)])
        self.assertEqual(s.extended_days_used, 2)
        self.assertEqual(s.extended_days_left, 0)
        self.assertEqual(s.daily_limit, rules.DAILY_DRIVE)

        s = summary(day + [(DRIVE, 270), (REST, 45), (DRIVE, 280)])
        self.assertEqual(s.extended_days_used, 1)
        self.assertEqual(s.daily_limit, rules.DAILY_DRIVE_EXTENDED)
        self.assertEqual(s.daily_left, 50 * MIN)


class WeeklyTest(unittest.TestCase):
    def test_week_start_is_monday_utc(self):
        self.assertEqual(rules.week_start(BASE + 3 * rules.DAY), BASE - 6 * HOUR)

    def test_weekly_drive_clipped_at_week_boundary(self):
        # неділя 23:00 UTC -> понеділок 01:00 UTC
        start = BASE - 7 * HOUR
        s = summary([(DRIVE, 120), (REST, 1)], start=start)
        self.assertEqual(s.week_drive, 60 * MIN)
        self.assertEqual(s.fortnight_drive, 120 * MIN)

    def test_weekly_rest_and_deadline(self):
        s = summary([(DRIVE, 60), (REST, 45 * 60), (DRIVE, 60)])
        self.assertEqual(s.last_weekly_rest_end, BASE + (60 + 45 * 60) * MIN)
        self.assertEqual(s.weekly_rest_deadline, s.last_weekly_rest_end + 6 * rules.DAY)

    def test_weekly_limit(self):
        day = [(DRIVE, 270), (REST, 45), (DRIVE, 270), (REST, 13 * 60 + 15)]
        s = summary(day * 6 + [(DRIVE, 30)])
        self.assertEqual(s.week_drive, 6 * 9 * HOUR + 30 * MIN)
        self.assertEqual(s.weekly_left, 90 * MIN)


class AlertsTest(unittest.TestCase):
    def test_break_soon_then_now(self):
        self.assertEqual(alert_ids(summary([(DRIVE, 200)])), [])
        self.assertIn("warn_break_soon", alert_ids(summary([(DRIVE, 240)])))
        alerts = rules.due_alerts(summary([(DRIVE, 270)]))
        brk = [a for a in alerts if a.text_id.startswith("warn_break")]
        self.assertEqual(len(brk), 1)
        self.assertEqual(brk[0].text_id, "warn_break_now")
        self.assertEqual(len(brk[0].covers), 2)

    def test_break_alert_key_changes_after_break(self):
        a1 = [a for a in rules.due_alerts(summary([(DRIVE, 245)])) if a.text_id == "warn_break_soon"][0]
        a2 = [a for a in rules.due_alerts(summary([(DRIVE, 245), (REST, 45), (DRIVE, 245)]))
              if a.text_id == "warn_break_soon"][0]
        self.assertNotEqual(a1.key, a2.key)

    def test_short_stop_keeps_break_alert_key(self):
        a1 = [a for a in rules.due_alerts(summary([(DRIVE, 245)])) if a.text_id == "warn_break_soon"][0]
        a2 = [a for a in rules.due_alerts(summary([(DRIVE, 245), (REST, 5), (DRIVE, 5)]))
              if a.text_id == "warn_break_soon"][0]
        self.assertEqual(a1.key, a2.key)

    def test_daily_alerts_with_extension(self):
        steps = [(DRIVE, 270), (REST, 45), (DRIVE, 270), (REST, 45)]
        self.assertIn("warn_daily_extended", alert_ids(summary(steps + [(DRIVE, 1)])))
        self.assertIn("warn_daily_over", alert_ids(summary(steps + [(DRIVE, 60)])))

    def test_daily_alerts_without_extension(self):
        day = [(DRIVE, 270), (REST, 45), (DRIVE, 270), (REST, 45), (DRIVE, 30), (REST, 11 * 60)]
        steps = day + day + [(DRIVE, 270), (REST, 45), (DRIVE, 270)]
        self.assertIn("warn_daily_over", alert_ids(summary(steps)))

    def test_shift_deadline_alert_while_working(self):
        self.assertIn("warn_shift_soon", alert_ids(summary([(WORK, 14 * 60 + 40)])))
        self.assertIn("warn_shift_over", alert_ids(summary([(WORK, 15 * 60)])))

    def test_rest_alerts(self):
        self.assertEqual(alert_ids(summary([(DRIVE, 200), (REST, 30)])), [])
        self.assertEqual(alert_ids(summary([(DRIVE, 200), (REST, 45)])), ["rest_break_done"])
        alerts = rules.due_alerts(summary([(DRIVE, 200), (REST, 11 * 60)]))
        self.assertEqual([a.text_id for a in alerts], ["rest_daily_done"])
        self.assertEqual(len(alerts[0].covers), 2)


class NormalizeTest(unittest.TestCase):
    def test_merges_and_clips(self):
        out = rules.normalize([
            Period(REST, 0, 100),
            Period(REST, 100, 200),
            Period(DRIVE, 150, 400),
            Period(DRIVE, 500, 900),
        ], now=800)
        self.assertEqual(out, [
            Period(REST, 0, 200),
            Period(DRIVE, 200, 400),
            Period(REST, 400, 500),
            Period(DRIVE, 500, 800),
        ])

    def test_idle_with_history_is_rest(self):
        s = rules.summarize([Period(DRIVE, BASE, BASE + HOUR)], BASE + 12 * HOUR, None)
        self.assertIsNone(s.kind)
        self.assertIsNone(s.shift_start)


if __name__ == "__main__":
    unittest.main()
