# -*- coding: utf-8 -*-
"""База даних SQLite / Database."""

import os
import sqlite3
from contextlib import closing, contextmanager

import config
import rules

_path = config.DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    chat_id INTEGER PRIMARY KEY,
    name TEXT,
    lang TEXT DEFAULT 'uk',
    tz TEXT,                        -- NULL -> config.DEFAULT_TZ
    state TEXT DEFAULT 'idle',      -- idle | drive | work | rest
    session_start INTEGER           -- unix timestamp початку поточного режиму
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    kind TEXT,                      -- drive | work | rest
    start_ts INTEGER,
    end_ts INTEGER,
    duration_min INTEGER
);
CREATE INDEX IF NOT EXISTS idx_history_chat_end ON history (chat_id, end_ts);
CREATE TABLE IF NOT EXISTS sent_alerts (
    chat_id INTEGER,
    alert_key TEXT,
    sent_ts INTEGER,
    PRIMARY KEY (chat_id, alert_key)
);
"""

DRIVER_FIELDS = ("name", "lang", "tz", "state", "session_start")


@contextmanager
def _conn():
    with closing(sqlite3.connect(_path, timeout=10)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:  # транзакція: commit або rollback
            yield conn


def init(path: str = None):
    global _path
    if path:
        _path = path
    folder = os.path.dirname(_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with _conn() as conn:
        conn.executescript(SCHEMA)
        # Міграція зі старої версії бота (один файл bot.py)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(drivers)")}
        if "tz" not in cols:
            conn.execute("ALTER TABLE drivers ADD COLUMN tz TEXT")
        conn.execute("UPDATE drivers SET state='drive' WHERE state='driving'")
        conn.execute("UPDATE drivers SET state='rest' WHERE state='resting'")


def get_driver(chat_id: int):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM drivers WHERE chat_id=?", (chat_id,)).fetchone()
    return dict(row) if row else None


def register_driver(chat_id: int, name: str, lang: str):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO drivers (chat_id, name, lang, state) VALUES (?, ?, ?, 'idle')",
            (chat_id, name, lang),
        )


def update_driver(chat_id: int, **fields):
    unknown = set(fields) - set(DRIVER_FIELDS)
    if unknown:
        raise ValueError(f"Unknown driver fields: {unknown}")
    sets = ", ".join(f"{k}=?" for k in fields)
    with _conn() as conn:
        conn.execute(f"UPDATE drivers SET {sets} WHERE chat_id=?", (*fields.values(), chat_id))


def last_history_end(chat_id: int):
    with _conn() as conn:
        row = conn.execute("SELECT MAX(end_ts) AS e FROM history WHERE chat_id=?", (chat_id,)).fetchone()
    return row["e"]


def switch_mode(chat_id: int, kind: str, at: int):
    """Закриває поточний режим (записує в історію) і відкриває новий з моменту at."""
    with _conn() as conn:
        row = conn.execute("SELECT state, session_start FROM drivers WHERE chat_id=?", (chat_id,)).fetchone()
        if row and row["state"] in rules.MODES and row["session_start"] and at > row["session_start"]:
            start = row["session_start"]
            conn.execute(
                "INSERT INTO history (chat_id, kind, start_ts, end_ts, duration_min) VALUES (?, ?, ?, ?, ?)",
                (chat_id, row["state"], start, at, (at - start) // 60),
            )
        conn.execute("UPDATE drivers SET state=?, session_start=? WHERE chat_id=?", (kind, at, chat_id))


def load_periods(chat_id: int, since: int) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT kind, start_ts, end_ts FROM history WHERE chat_id=? AND end_ts>=? ORDER BY start_ts",
            (chat_id, since),
        ).fetchall()
    return [rules.Period(r["kind"], r["start_ts"], r["end_ts"]) for r in rows if r["kind"] in rules.MODES]


def current_mode(driver):
    """(kind, since) поточного режиму або None."""
    if driver["state"] in rules.MODES and driver["session_start"]:
        return driver["state"], driver["session_start"]
    return None


def load_summary(driver, now: int) -> rules.Summary:
    since = now - config.HISTORY_DAYS * rules.DAY
    return rules.summarize(load_periods(driver["chat_id"], since), now, current_mode(driver))


def drivers_to_check(rest_since: int) -> list:
    """Водії, яким можуть бути потрібні попередження: в дорозі / на роботі
    або на відпочинку, що почався не раніше rest_since."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM drivers WHERE state IN ('drive', 'work') "
            "OR (state='rest' AND session_start>=?)",
            (rest_since,),
        ).fetchall()
    return [dict(r) for r in rows]


def sent_alert_keys(chat_id: int) -> set:
    with _conn() as conn:
        rows = conn.execute("SELECT alert_key FROM sent_alerts WHERE chat_id=?", (chat_id,)).fetchall()
    return {r["alert_key"] for r in rows}


def mark_alerts_sent(chat_id: int, keys, now: int):
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO sent_alerts (chat_id, alert_key, sent_ts) VALUES (?, ?, ?)",
            [(chat_id, k, now) for k in keys],
        )


def purge_sent_alerts(older_than: int):
    with _conn() as conn:
        conn.execute("DELETE FROM sent_alerts WHERE sent_ts<?", (older_than,))
