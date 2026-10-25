# -*- coding: utf-8 -*-
"""
Правила режиму праці та відпочинку водія (Регламент (ЄС) 561/2006 / AETR).

Розрахунок спрощений і НЕ є юридичною консультацією. Модуль не залежить
від Telegram і бази даних: на вхід — періоди активності, на вихід — підсумок
(Summary) і попередження, які час надіслати. Усі часи — unix timestamp у секундах.

Що враховується:
- безперервне водіння 4 год 30 хв, перерва 45 хв або 15 + 30 хв;
- денне водіння 9 год (10 год — не більше 2 разів на тиждень);
- денний відпочинок 11 год (скорочений 9 год — не більше 3 разів між
  тижневими відпочинками, розділений 3 + 9 год) у межах 24 год від початку зміни;
- тижневе водіння 56 год і 90 год за два тижні поспіль;
- тижневий відпочинок (24/45 год) — не пізніше ніж через 6 діб після попереднього.

Тиждень рахується як у тахографі: з понеділка 00:00 UTC.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

DRIVE = "drive"   # водіння
WORK = "work"     # інша робота (завантаження, огляд, оформлення...)
REST = "rest"     # перерва / відпочинок
MODES = (DRIVE, WORK, REST)

MIN = 60
HOUR = 60 * MIN
DAY = 24 * HOUR
WEEK = 7 * DAY

MAX_CONTINUOUS_DRIVE = 4 * HOUR + 30 * MIN
BREAK_FULL = 45 * MIN
BREAK_SPLIT_FIRST = 15 * MIN
BREAK_SPLIT_SECOND = 30 * MIN

DAILY_DRIVE = 9 * HOUR
DAILY_DRIVE_EXTENDED = 10 * HOUR
MAX_EXTENDED_DAYS_PER_WEEK = 2

DAILY_REST = 11 * HOUR
DAILY_REST_REDUCED = 9 * HOUR
DAILY_REST_SPLIT_FIRST = 3 * HOUR
MAX_REDUCED_DAILY_RESTS = 3
SHIFT_WINDOW = 24 * HOUR

WEEKLY_REST = 45 * HOUR
WEEKLY_REST_REDUCED = 24 * HOUR
MAX_TIME_BETWEEN_WEEKLY_RESTS = 6 * DAY

WEEKLY_DRIVE = 56 * HOUR
FORTNIGHT_DRIVE = 90 * HOUR

# За скільки попереджати
WARN_BREAK_BEFORE = 30 * MIN
WARN_DAILY_BEFORE = 30 * MIN
WARN_WEEKLY_BEFORE = 60 * MIN
WARN_SHIFT_END_BEFORE = 30 * MIN
WARN_WEEKLY_REST_BEFORE = 2 * HOUR


@dataclass(frozen=True)
class Period:
    kind: str
    start: int
    end: int

    @property
    def duration(self) -> int:
        return self.end - self.start


@dataclass
class _Shift:
    start: int
    drive: int = 0
    has_3h_rest: bool = False


@dataclass
class Summary:
    now: int
    week_start: int
    kind: Optional[str] = None          # поточний режим (None — ще не вибрано)
    kind_since: Optional[int] = None

    continuous_drive: int = 0           # водіння після останньої зарахованої перерви
    split_first_taken: bool = False     # перша частина розділеної перерви (15 хв) вже є
    break_anchor: int = 0               # кінець останньої зарахованої перерви
    current_rest: int = 0               # тривалість поточного відпочинку
    rest_break_target: int = 0          # скільки треба відпочити, щоб це була перерва (0 — не потрібно)

    shift_start: Optional[int] = None   # початок зміни (кінець останнього денного відпочинку)
    shift_drive: int = 0
    shift_has_3h_rest: bool = False
    extended_days_used: int = 0         # подовжені (10 год) дні цього тижня, крім поточної зміни
    reduced_rests_used: int = 0         # скорочені денні відпочинки після тижневого

    week_drive: int = 0
    fortnight_drive: int = 0
    last_weekly_rest_end: Optional[int] = None

    # --- похідні значення ---

    @property
    def extended_days_left(self) -> int:
        return max(0, MAX_EXTENDED_DAYS_PER_WEEK - self.extended_days_used)

    @property
    def reduced_rests_left(self) -> int:
        return max(0, MAX_REDUCED_DAILY_RESTS - self.reduced_rests_used)

    @property
    def daily_limit(self) -> int:
        if self.shift_drive >= DAILY_DRIVE and self.extended_days_left > 0:
            return DAILY_DRIVE_EXTENDED
        return DAILY_DRIVE

    @property
    def continuous_left(self) -> int:
        return max(0, MAX_CONTINUOUS_DRIVE - self.continuous_drive)

    @property
    def daily_left(self) -> int:
        return max(0, self.daily_limit - self.shift_drive)

    @property
    def weekly_left(self) -> int:
        return max(0, min(WEEKLY_DRIVE - self.week_drive, FORTNIGHT_DRIVE - self.fortnight_drive))

    @property
    def drive_left(self) -> int:
        return min(self.continuous_left, self.daily_left, self.weekly_left)

    @property
    def break_needed(self) -> int:
        """Скільки ще відпочивати, щоб поточний відпочинок зарахувався як перерва."""
        if self.kind != REST or not self.rest_break_target:
            return 0
        return max(0, self.rest_break_target - self.current_rest)

    @property
    def rest_deadline_regular(self) -> Optional[int]:
        """Найпізніший початок повного денного відпочинку (11 год або 9 год після 3 год)."""
        if self.shift_start is None:
            return None
        need = DAILY_REST_REDUCED if self.shift_has_3h_rest else DAILY_REST
        return self.shift_start + SHIFT_WINDOW - need

    @property
    def rest_deadline(self) -> Optional[int]:
        """Найпізніший допустимий початок денного відпочинку (з урахуванням скороченого)."""
        if self.shift_start is None:
            return None
        if self.shift_has_3h_rest or self.reduced_rests_left > 0:
            need = DAILY_REST_REDUCED
        else:
            need = DAILY_REST
        return self.shift_start + SHIFT_WINDOW - need

    @property
    def weekly_rest_deadline(self) -> Optional[int]:
        if self.last_weekly_rest_end is None:
            return None
        return self.last_weekly_rest_end + MAX_TIME_BETWEEN_WEEKLY_RESTS


def week_start(ts: int) -> int:
    """Понеділок 00:00 UTC тижня, в який потрапляє ts."""
    d = datetime.fromtimestamp(ts, timezone.utc)
    monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(monday.timestamp())


def normalize(periods, now: int) -> list:
    """Сортує періоди, обрізає по now і перекриття, заповнює проміжки відпочинком
    (картка вийнята = відпочинок) і зливає сусідні періоди однакового типу."""
    out = []
    for p in sorted(periods, key=lambda p: (p.start, p.end)):
        start, end = p.start, min(p.end, now)
        if out:
            start = max(start, out[-1].end)
        if end <= start:
            continue
        if out and start > out[-1].end:
            _append(out, Period(REST, out[-1].end, start))
        _append(out, Period(p.kind, start, end))
    return out


def _append(out: list, p: Period):
    if out and out[-1].kind == p.kind and out[-1].end == p.start:
        out[-1] = Period(p.kind, out[-1].start, p.end)
    else:
        out.append(p)


def _drive_between(periods, start: int, end: int) -> int:
    total = 0
    for p in periods:
        if p.kind == DRIVE:
            total += max(0, min(p.end, end) - max(p.start, start))
    return total


def summarize(history, now: int, current=None) -> Summary:
    """
    history — завершені періоди (Period), current — (kind, since) поточного режиму
    або None, якщо режим ще не вибрано.
    """
    s = Summary(now=now, week_start=week_start(now))
    periods = list(history)
    if current:
        s.kind, s.kind_since = current
        periods.append(Period(s.kind, s.kind_since, now))
    elif periods:
        periods.append(Period(REST, max(p.end for p in periods), now))
    periods = normalize(periods, now)
    if not periods:
        return s

    last = periods[-1]
    open_index = len(periods) - 1 if (s.kind and last.kind == s.kind and last.end == now) else None

    cont = 0
    split_first = False
    anchor = 0
    shift = None
    shifts = []
    reduced = 0
    last_weekly_end = None

    for i, p in enumerate(periods):
        is_open = i == open_index
        if p.kind != REST:
            if shift is None:
                shift = _Shift(start=p.start)
            if p.kind == DRIVE:
                cont += p.duration
                shift.drive += p.duration
            continue

        d = p.duration
        if is_open:
            s.current_rest = d
            if cont > 0:
                s.rest_break_target = BREAK_SPLIT_SECOND if split_first else BREAK_FULL

        # Перерва: 45 хв одразу або 15 хв + 30 хв (саме в такому порядку)
        if d >= BREAK_FULL or (split_first and d >= BREAK_SPLIT_SECOND):
            cont = 0
            split_first = False
            anchor = p.end
        elif d >= BREAK_SPLIT_FIRST:
            split_first = True

        # Денний / тижневий відпочинок завершує зміну
        if d >= DAILY_REST_REDUCED:
            if d >= WEEKLY_REST_REDUCED:
                reduced = 0
                last_weekly_end = p.end
            elif d < DAILY_REST and not is_open and not (shift and shift.has_3h_rest):
                reduced += 1
            if shift is not None:
                shifts.append(shift)
                shift = None
        elif d >= DAILY_REST_SPLIT_FIRST and shift is not None:
            shift.has_3h_rest = True

    if s.kind == REST and open_index is None and cont > 0:
        # Відпочинок щойно почався (нульова тривалість) — він ще не в periods
        s.rest_break_target = BREAK_SPLIT_SECOND if split_first else BREAK_FULL

    s.continuous_drive = cont
    s.split_first_taken = split_first
    s.break_anchor = anchor
    if shift is not None:
        s.shift_start = shift.start
        s.shift_drive = shift.drive
        s.shift_has_3h_rest = shift.has_3h_rest
    s.extended_days_used = sum(1 for sh in shifts if sh.start >= s.week_start and sh.drive > DAILY_DRIVE)
    s.reduced_rests_used = reduced
    s.week_drive = _drive_between(periods, s.week_start, now)
    s.fortnight_drive = _drive_between(periods, s.week_start - WEEK, now)
    s.last_weekly_rest_end = last_weekly_end
    return s


# -------------------------------------------------------------------------
# ПОПЕРЕДЖЕННЯ / ALERTS
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class Alert:
    text_id: str                    # ключ тексту в texts.TEXTS
    key: str                        # унікальний ключ, щоб не надсилати двічі
    covers: tuple = field(default=())  # ключі нижчих порогів, які теж вважаємо надісланими
    at: Optional[int] = None        # час для підстановки в текст (дедлайн)


def _pick(thresholds, anchor, at=None) -> Optional[Alert]:
    """З упорядкованих порогів (text_id, досягнуто?) обирає найвищий досягнутий.
    Нижчі пороги позначаються надісланими разом з ним — щоб після простою бота
    водій не отримав пачку застарілих повідомлень."""
    reached = [tid for tid, ok in thresholds if ok]
    if not reached:
        return None
    keys = tuple(f"{tid}:{anchor}" for tid in reached)
    return Alert(text_id=reached[-1], key=keys[-1], covers=keys, at=at)


def due_alerts(s: Summary) -> list:
    alerts = []
    now = s.now

    if s.kind == DRIVE:
        alerts.append(_pick([
            ("warn_break_soon", s.continuous_left <= WARN_BREAK_BEFORE),
            ("warn_break_now", s.continuous_left == 0),
        ], s.break_anchor))

        d = s.shift_drive
        if s.extended_days_left > 0:
            daily = [
                ("warn_daily_soon", d >= DAILY_DRIVE - WARN_DAILY_BEFORE),
                ("warn_daily_extended", d >= DAILY_DRIVE),
                ("warn_daily_ext_soon", d >= DAILY_DRIVE_EXTENDED - WARN_DAILY_BEFORE),
                ("warn_daily_over", d >= DAILY_DRIVE_EXTENDED),
            ]
        else:
            daily = [
                ("warn_daily_soon", d >= DAILY_DRIVE - WARN_DAILY_BEFORE),
                ("warn_daily_over", d >= DAILY_DRIVE),
            ]
        alerts.append(_pick(daily, s.shift_start))

        alerts.append(_pick([
            ("warn_weekly_soon", s.weekly_left <= WARN_WEEKLY_BEFORE),
            ("warn_weekly_over", s.weekly_left == 0),
        ], s.week_start))

    if s.kind in (DRIVE, WORK):
        deadline = s.rest_deadline
        if deadline is not None:
            alerts.append(_pick([
                ("warn_shift_soon", now >= deadline - WARN_SHIFT_END_BEFORE),
                ("warn_shift_over", now >= deadline),
            ], s.shift_start, at=deadline))

        deadline = s.weekly_rest_deadline
        if deadline is not None:
            alerts.append(_pick([
                ("warn_weekly_rest_soon", now >= deadline - WARN_WEEKLY_REST_BEFORE),
                ("warn_weekly_rest_over", now >= deadline),
            ], s.last_weekly_rest_end, at=deadline))

    if s.kind == REST:
        alerts.append(_pick([
            ("rest_break_done", s.rest_break_target > 0 and s.current_rest >= s.rest_break_target),
            ("rest_daily_done", s.current_rest >= DAILY_REST),
        ], s.kind_since))

    return [a for a in alerts if a is not None]
