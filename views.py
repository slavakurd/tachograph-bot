# -*- coding: utf-8 -*-
"""Тексти повідомлень на основі підсумку rules.Summary / Message rendering."""

from datetime import datetime

import config
import rules
from texts import fmt_duration, fmt_time, t


def driver_zone(driver):
    return config.get_zone(driver.get("tz") or config.DEFAULT_TZ)


def driver_zone_name(driver) -> str:
    name = driver.get("tz") or config.DEFAULT_TZ
    return name if config.is_valid_zone(name) else "UTC"


def _limit_lines(s: rules.Summary, lang: str, tz, now: int, starting: bool = False) -> list:
    """Рядки про ліміти водіння (без перерви / зміна / тиждень / дедлайни).
    Під час відпочинку дедлайни на початок відпочинку не показуємо — він уже триває."""
    resting = s.kind == rules.REST
    d = lambda sec: fmt_duration(lang, sec)  # noqa: E731
    lines = [t(lang, "line_cont", used=d(s.continuous_drive), left=d(s.continuous_left))]
    if s.split_first_taken and s.continuous_drive > 0 and not resting:
        lines.append(t(lang, "line_split"))
    lines.append(t(lang, "line_daily", used=d(s.shift_drive), limit=d(s.daily_limit), left=d(s.daily_left)))
    if s.extended_days_used or s.shift_drive > rules.DAILY_DRIVE:
        used = s.extended_days_used + (1 if s.shift_drive > rules.DAILY_DRIVE else 0)
        lines.append(t(lang, "line_ext", used=used))
    lines.append(t(lang, "line_week", used=d(s.week_drive), used2=d(s.fortnight_drive)))

    if s.rest_deadline is not None and not resting:
        if s.rest_deadline != s.rest_deadline_regular:
            lines.append(t(
                lang, "line_rest_deadline_both",
                time=fmt_time(s.rest_deadline_regular, tz, now),
                time_reduced=fmt_time(s.rest_deadline, tz, now),
                left=s.reduced_rests_left,
            ))
        else:
            lines.append(t(lang, "line_rest_deadline", time=fmt_time(s.rest_deadline, tz, now)))
    if s.weekly_rest_deadline is not None and not resting:
        lines.append(t(lang, "line_weekly_rest_deadline", time=fmt_time(s.weekly_rest_deadline, tz, now)))

    if s.drive_left > 0:
        key = "line_drive_left_if" if starting else "line_drive_left"
        lines.append(t(lang, key, left=d(s.drive_left)))
    else:
        lines.append(t(lang, "line_drive_none"))
    return lines


def _rest_lines(s: rules.Summary, lang: str, tz, now: int) -> list:
    d = lambda sec: fmt_duration(lang, sec)  # noqa: E731
    rest_start = now - s.current_rest
    lines = []
    if s.break_needed > 0:
        lines.append(t(lang, "rest_break_left", target=d(s.rest_break_target), left=d(s.break_needed)))
    elif s.rest_break_target:
        lines.append(t(lang, "rest_break_ok"))

    r = s.current_rest
    if r >= rules.BREAK_FULL or not s.rest_break_target:
        if r < rules.DAILY_REST:
            lines.append(t(lang, "rest_daily_progress", time=fmt_time(rest_start + rules.DAILY_REST, tz, now)))
            if r < rules.DAILY_REST_REDUCED and s.reduced_rests_left > 0:
                lines.append(t(
                    lang, "rest_daily_reduced",
                    time=fmt_time(rest_start + rules.DAILY_REST_REDUCED, tz, now),
                    left=s.reduced_rests_left,
                ))
        elif r < rules.WEEKLY_REST_REDUCED:
            lines.append(t(lang, "rest_daily_ok"))
            lines.append(t(
                lang, "rest_weekly_progress",
                time24=fmt_time(rest_start + rules.WEEKLY_REST_REDUCED, tz, now),
                time45=fmt_time(rest_start + rules.WEEKLY_REST, tz, now),
            ))
        elif r < rules.WEEKLY_REST:
            lines.append(t(lang, "rest_weekly_reduced_ok", time45=fmt_time(rest_start + rules.WEEKLY_REST, tz, now)))
        else:
            lines.append(t(lang, "rest_weekly_ok"))
    return lines


def status_text(s: rules.Summary, driver, now: int) -> str:
    lang, tz = driver["lang"], driver_zone(driver)
    if s.kind is None:
        return t(lang, "now_idle")

    since = fmt_time(s.kind_since, tz, now)
    head = t(lang, f"now_{s.kind}", time=since, dur=fmt_duration(lang, now - s.kind_since))
    blocks = [[head]]
    if s.kind == rules.REST:
        blocks.append(_rest_lines(s, lang, tz, now))
    blocks.append(_limit_lines(s, lang, tz, now, starting=(s.kind != rules.DRIVE)))
    return "\n\n".join("\n".join(b) for b in blocks if b)


def mode_started_text(kind: str, before: rules.Summary, after: rules.Summary, driver, at: int, now: int) -> str:
    """Відповідь на перемикання режиму. before — підсумок на момент перемикання
    (ще в старому режимі), after — зараз, вже в новому."""
    lang, tz = driver["lang"], driver_zone(driver)
    d = lambda sec: fmt_duration(lang, sec)  # noqa: E731
    lines = [t(lang, f"{kind}_started", time=fmt_time(at, tz, now))]

    if kind == rules.DRIVE:
        if before.kind == rules.REST and before.break_needed > 0:
            lines.append(t(lang, "break_incomplete", rested=d(before.current_rest), target=d(before.rest_break_target)))
        lines.append("")
        lines.extend(_limit_lines(after, lang, tz, now))
    elif kind == rules.REST:
        if before.kind == rules.DRIVE:
            lines.append(t(lang, "drive_lasted", dur=d(at - before.kind_since)))
        if after.rest_break_target and after.break_needed > 0:
            lines.append(t(lang, "rest_started_break", target=d(after.rest_break_target)))
    return "\n".join(lines)


def history_text(periods, s: rules.Summary, driver, now: int, limit: int = 15) -> str:
    lang, tz = driver["lang"], driver_zone(driver)
    items = [(p.kind, p.start, p.end, False) for p in periods]
    if s.kind is not None and s.kind_since < now:
        items.append((s.kind, s.kind_since, now, True))
    items = items[-limit:]
    if not items:
        return t(lang, "history_empty")

    icons = {rules.DRIVE: "🚛", rules.WORK: "🔧", rules.REST: "🛑"}
    lines = [t(lang, "history_header")]
    for kind, start, end, is_open in items:
        start_str = datetime.fromtimestamp(start, tz).strftime("%d.%m %H:%M")
        end_str = t(lang, "history_now") if is_open else fmt_time(end, tz, start)
        lines.append(f"{icons.get(kind, '•')} {t(lang, f'mode_{kind}')}: {start_str}–{end_str} · {fmt_duration(lang, end - start)}")
    return "\n".join(lines)


def alert_text(alert: rules.Alert, s: rules.Summary, driver, now: int) -> str:
    lang, tz = driver["lang"], driver_zone(driver)
    d = lambda sec: fmt_duration(lang, sec)  # noqa: E731
    params = {"name": driver.get("name") or "", "time": fmt_time(alert.at, tz, now) if alert.at else ""}

    tid = alert.text_id
    if tid == "warn_break_soon":
        params["left"] = d(s.continuous_left)
    elif tid == "warn_break_now":
        params["target"] = d(rules.BREAK_SPLIT_SECOND if s.split_first_taken else rules.BREAK_FULL)
    elif tid == "warn_daily_soon":
        params["left"] = d(max(0, rules.DAILY_DRIVE - s.shift_drive))
    elif tid == "warn_daily_ext_soon":
        params["left"] = d(max(0, rules.DAILY_DRIVE_EXTENDED - s.shift_drive))
    elif tid == "warn_weekly_soon":
        params["left"] = d(s.weekly_left)

    text = t(lang, tid, **params)
    if tid == "warn_daily_soon":
        if s.extended_days_left > 0:
            text += "\n" + t(lang, "warn_daily_soon_ext", ext=s.extended_days_left)
        else:
            text += "\n" + t(lang, "warn_daily_soon_noext")
    return text
