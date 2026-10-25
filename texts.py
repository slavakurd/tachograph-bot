# -*- coding: utf-8 -*-
"""Тексти та форматування / I18N and formatting."""

from datetime import datetime

LANGS = ("uk", "en")
DEFAULT_LANG = "uk"

HELP_UK = (
    "Натискайте кнопку щоразу, коли змінюєте режим:\n"
    "🚛 Їду — почали кермувати (/drive)\n"
    "🔧 Інша робота — завантаження, огляд, документи (/work)\n"
    "🛑 Відпочинок — перерва або відпочинок (/stop)\n"
    "📊 Статус — скільки ще можна їхати (/status)\n"
    "📜 Історія — останні записи (/history)\n\n"
    "Забули натиснути вчасно? Додайте, скільки хвилин тому це було: /stop 10\n"
    "Часовий пояс: /tz (зараз {tz})\n"
    "Мова: /lang\n\n"
    "Я нагадаю:\n"
    "• за 30 хв до 4 год 30 хв безперервного водіння і коли час зупинятись;\n"
    "• коли перерву (45 хв або 15 + 30 хв) виконано;\n"
    "• про денну (9/10 год), тижневу (56 год) і двотижневу (90 год) норми;\n"
    "• коли час починати денний і тижневий відпочинок.\n\n"
    "⚠️ Розрахунок спрощений і не замінює тахограф та офіційні правила "
    "(Регламент (ЄС) 561/2006, AETR)."
)

HELP_EN = (
    "Press a button every time you change activity:\n"
    "🚛 Driving — you started driving (/drive)\n"
    "🔧 Other work — loading, checks, paperwork (/work)\n"
    "🛑 Rest — break or rest (/stop)\n"
    "📊 Status — how much longer you may drive (/status)\n"
    "📜 History — recent entries (/history)\n\n"
    "Forgot to press in time? Add how many minutes ago it was: /stop 10\n"
    "Time zone: /tz (now {tz})\n"
    "Language: /lang\n\n"
    "I'll remind you:\n"
    "• 30 min before 4h 30m of continuous driving and when it's time to stop;\n"
    "• when your break (45 min or 15 + 30 min) is complete;\n"
    "• about the daily (9/10h), weekly (56h) and two-week (90h) limits;\n"
    "• when it's time to start your daily and weekly rest.\n\n"
    "⚠️ This is a simplified calculation and does not replace the tachograph or the "
    "official rules (Regulation (EC) 561/2006, AETR)."
)

TEXTS = {
    "uk": {
        "welcome": "👋 Вітаю, {name}!\n\nЯ бот-нагадувач режиму праці та відпочинку водія (тахограф).\n\n" + HELP_UK,
        "help": HELP_UK,
        "lang_set": "🌐 Мову встановлено: Українська",
        "tz_current": "🕒 Часовий пояс: {tz} (зараз {time}).\nЗмінити: /tz Europe/Warsaw",
        "tz_set": "🕒 Часовий пояс встановлено: {tz} (зараз {time}).",
        "tz_bad": "Невідомий часовий пояс. Приклади: Europe/Kyiv, Europe/Warsaw, Europe/Berlin, Europe/Madrid.",
        "bad_minutes": "Не зрозумів, скільки хвилин тому. Приклад: /stop 10 (від 1 до 720 хв).",
        "too_early": "Не можна раніше {time} — тоді почався попередній запис.",
        "already": "Ви вже в цьому режимі з {time}.",

        "mode_drive": "Водіння",
        "mode_work": "Інша робота",
        "mode_rest": "Відпочинок",

        "drive_started": "🚛 Водіння з {time}.",
        "work_started": "🔧 Інша робота з {time}.\nЦе не перерва — лічильник безперервного водіння не обнуляється.",
        "rest_started": "🛑 Відпочинок з {time}.",
        "drive_lasted": "Водіння тривало {dur}.",
        "rest_started_break": "Для перерви потрібно відпочити {target} — я повідомлю, коли можна їхати далі.",
        "break_incomplete": "⚠️ Перерву не завершено: відпочили {rested} з {target}, тому лічильник не обнулено.",

        "now_drive": "🚛 Зараз: водіння з {time} ({dur})",
        "now_work": "🔧 Зараз: інша робота з {time} ({dur})",
        "now_rest": "🛑 Зараз: відпочинок з {time} ({dur})",
        "now_idle": "😴 Режим ще не вибрано. Натисніть «🚛 Їду», коли вирушите в дорогу.",

        "line_cont": "⏱ Без перерви: {used} з 4 год 30 хв (залишилось {left})",
        "line_split": "    Перша частина перерви (15 хв) вже є — далі достатньо 30 хв.",
        "line_daily": "📅 За зміну: {used} з {limit} (залишилось {left})",
        "line_ext": "    Подовжених днів (10 год) цього тижня: {used} з 2",
        "line_week": "🗓 За тиждень: {used} з 56 год; за 2 тижні: {used2} з 90 год",
        "line_rest_deadline": "🏁 Денний відпочинок почати не пізніше {time}",
        "line_rest_deadline_both": "🏁 Денний відпочинок почати не пізніше: 11 год — {time}, скорочений 9 год — {time_reduced} (доступно ще {left} з 3)",
        "line_weekly_rest_deadline": "🛏 Тижневий відпочинок почати не пізніше {time}",
        "line_drive_left": "✅ Можна їхати ще: {left}",
        "line_drive_left_if": "🚛 Якщо поїхати зараз — можна до {left}",
        "line_drive_none": "⛔ Ліміт водіння вичерпано — потрібен відпочинок.",

        "rest_break_left": "⏳ До завершення перерви ({target}) залишилось {left}",
        "rest_break_ok": "✅ Перерву виконано — лічильник безперервного водіння обнулено.",
        "rest_daily_progress": "🛏 Денний відпочинок 11 год буде виконано о {time}",
        "rest_daily_reduced": "    Скорочений 9 год — о {time} (доступно ще {left} з 3)",
        "rest_daily_ok": "✅ Денний відпочинок (11 год) виконано.",
        "rest_weekly_progress": "🛏 Тижневий відпочинок: 24 год — {time24}, 45 год — {time45}",
        "rest_weekly_reduced_ok": "✅ Скорочений тижневий відпочинок (24 год) виконано; повний 45 год — {time45}",
        "rest_weekly_ok": "✅ Тижневий відпочинок (45 год) виконано.",

        "warn_break_soon": "⚠️ {name}, до обов'язкової перерви залишилось ~{left}.\nПочинайте шукати місце для безпечної зупинки.",
        "warn_break_now": "🛑 ЧАС ЗУПИНИТИСЬ, {name}!\nБезперервне водіння досягло 4 год 30 хв — потрібна перерва {target}.\nНатисніть «🛑 Відпочинок», коли зупинитесь.",
        "warn_daily_soon": "⚠️ {name}, до денної норми водіння (9 год) залишилось ~{left}.",
        "warn_daily_soon_ext": "Подовжити до 10 год цього тижня можна ще {ext} раз(и).",
        "warn_daily_soon_noext": "Подовження до 10 год цього тижня вже використано — плануйте завершення зміни.",
        "warn_daily_extended": "⚠️ {name}, ви проїхали 9 год — це подовжений день (максимум 10 год, не більше 2 разів на тиждень).",
        "warn_daily_ext_soon": "⚠️ {name}, до максимуму подовженого дня (10 год) залишилось ~{left}.",
        "warn_daily_over": "🛑 {name}, денну норму водіння вичерпано. Потрібен денний відпочинок (11 год, мінімум 9 год).",
        "warn_weekly_soon": "⚠️ {name}, до тижневого ліміту водіння залишилось ~{left} (56 год/тиждень, 90 год/2 тижні).",
        "warn_weekly_over": "🛑 {name}, тижневий ліміт водіння вичерпано (56 год/тиждень або 90 год/2 тижні).",
        "warn_shift_soon": "⚠️ {name}, денний відпочинок треба почати до {time} (24 год від початку зміни).",
        "warn_shift_over": "🛑 {name}, час починати денний відпочинок — 24 год від початку зміни минають.",
        "warn_weekly_rest_soon": "⚠️ {name}, тижневий відпочинок треба почати до {time} (6 діб після попереднього).",
        "warn_weekly_rest_over": "🛑 {name}, минуло 6 діб після тижневого відпочинку — час починати тижневий відпочинок.",
        "rest_break_done": "✅ {name}, перерву виконано — можна продовжувати рух.\nНатисніть «🚛 Їду», коли вирушите.",
        "rest_daily_done": "✅ {name}, денний відпочинок 11 год виконано.",

        "history_empty": "Історія поки порожня.",
        "history_header": "📜 Останні записи:",
        "history_now": "зараз",

        "btn_drive": "🚛 Їду",
        "btn_work": "🔧 Інша робота",
        "btn_rest": "🛑 Відпочинок",
        "btn_status": "📊 Статус",
        "btn_history": "📜 Історія",
        "btn_help": "❓ Довідка",

        "cmd_drive": "Почав їхати",
        "cmd_work": "Інша робота",
        "cmd_stop": "Зупинився / відпочинок",
        "cmd_status": "Скільки ще можна їхати",
        "cmd_history": "Історія",
        "cmd_tz": "Часовий пояс",
        "cmd_lang": "Мова / Language",
        "cmd_help": "Довідка",

        "dur_h": "{h} год",
        "dur_m": "{m} хв",
        "dur_hm": "{h} год {m} хв",
    },
    "en": {
        "welcome": "👋 Hello, {name}!\n\nI'm a tachograph driving and rest time reminder bot.\n\n" + HELP_EN,
        "help": HELP_EN,
        "lang_set": "🌐 Language set to: English",
        "tz_current": "🕒 Time zone: {tz} (now {time}).\nChange it: /tz Europe/Warsaw",
        "tz_set": "🕒 Time zone set: {tz} (now {time}).",
        "tz_bad": "Unknown time zone. Examples: Europe/Kyiv, Europe/Warsaw, Europe/Berlin, Europe/Madrid.",
        "bad_minutes": "I didn't get how many minutes ago. Example: /stop 10 (1 to 720 min).",
        "too_early": "Can't be earlier than {time} — the previous entry started then.",
        "already": "You're already in this mode since {time}.",

        "mode_drive": "Driving",
        "mode_work": "Other work",
        "mode_rest": "Rest",

        "drive_started": "🚛 Driving since {time}.",
        "work_started": "🔧 Other work since {time}.\nThis is not a break — the continuous driving counter is not reset.",
        "rest_started": "🛑 Rest since {time}.",
        "drive_lasted": "You drove for {dur}.",
        "rest_started_break": "A break requires {target} of rest — I'll tell you when you can continue.",
        "break_incomplete": "⚠️ Break not complete: you rested {rested} of {target}, so the counter was not reset.",

        "now_drive": "🚛 Now: driving since {time} ({dur})",
        "now_work": "🔧 Now: other work since {time} ({dur})",
        "now_rest": "🛑 Now: resting since {time} ({dur})",
        "now_idle": "😴 No activity selected yet. Press «🚛 Driving» when you hit the road.",

        "line_cont": "⏱ Without a break: {used} of 4h 30m ({left} left)",
        "line_split": "    First part of a split break (15 min) is done — 30 min is enough next.",
        "line_daily": "📅 This shift: {used} of {limit} ({left} left)",
        "line_ext": "    Extended (10h) days this week: {used} of 2",
        "line_week": "🗓 This week: {used} of 56h; two weeks: {used2} of 90h",
        "line_rest_deadline": "🏁 Start your daily rest no later than {time}",
        "line_rest_deadline_both": "🏁 Start your daily rest no later than: 11h — {time}, reduced 9h — {time_reduced} ({left} of 3 left)",
        "line_weekly_rest_deadline": "🛏 Start your weekly rest no later than {time}",
        "line_drive_left": "✅ You may drive another: {left}",
        "line_drive_left_if": "🚛 If you start now — up to {left}",
        "line_drive_none": "⛔ Driving limit reached — rest is required.",

        "rest_break_left": "⏳ Time left until the break ({target}) is complete: {left}",
        "rest_break_ok": "✅ Break complete — the continuous driving counter is reset.",
        "rest_daily_progress": "🛏 11h daily rest complete at {time}",
        "rest_daily_reduced": "    Reduced 9h — at {time} ({left} of 3 left)",
        "rest_daily_ok": "✅ Daily rest (11h) complete.",
        "rest_weekly_progress": "🛏 Weekly rest: 24h — {time24}, 45h — {time45}",
        "rest_weekly_reduced_ok": "✅ Reduced weekly rest (24h) complete; full 45h — {time45}",
        "rest_weekly_ok": "✅ Weekly rest (45h) complete.",

        "warn_break_soon": "⚠️ {name}, about {left} left until a mandatory break.\nStart looking for a safe place to stop.",
        "warn_break_now": "🛑 TIME TO STOP, {name}!\nContinuous driving has reached 4h 30m — a {target} break is required.\nPress «🛑 Rest» once you've stopped.",
        "warn_daily_soon": "⚠️ {name}, about {left} left until the daily driving limit (9h).",
        "warn_daily_soon_ext": "You can still extend to 10h {ext} more time(s) this week.",
        "warn_daily_soon_noext": "Both 10h extensions are used this week — plan to end your shift.",
        "warn_daily_extended": "⚠️ {name}, you've driven 9h — this is an extended day (max 10h, at most twice a week).",
        "warn_daily_ext_soon": "⚠️ {name}, about {left} left until the extended day maximum (10h).",
        "warn_daily_over": "🛑 {name}, the daily driving limit is reached. Daily rest is required (11h, at least 9h).",
        "warn_weekly_soon": "⚠️ {name}, about {left} left until the weekly driving limit (56h/week, 90h/2 weeks).",
        "warn_weekly_over": "🛑 {name}, the weekly driving limit is reached (56h/week or 90h/2 weeks).",
        "warn_shift_soon": "⚠️ {name}, you must start your daily rest by {time} (24h from the start of the shift).",
        "warn_shift_over": "🛑 {name}, time to start your daily rest — the 24h shift window is ending.",
        "warn_weekly_rest_soon": "⚠️ {name}, you must start your weekly rest by {time} (6 days after the previous one).",
        "warn_weekly_rest_over": "🛑 {name}, 6 days have passed since your weekly rest — time to start it.",
        "rest_break_done": "✅ {name}, break complete — you may continue driving.\nPress «🚛 Driving» when you set off.",
        "rest_daily_done": "✅ {name}, 11h daily rest complete.",

        "history_empty": "History is empty so far.",
        "history_header": "📜 Recent entries:",
        "history_now": "now",

        "btn_drive": "🚛 Driving",
        "btn_work": "🔧 Other work",
        "btn_rest": "🛑 Rest",
        "btn_status": "📊 Status",
        "btn_history": "📜 History",
        "btn_help": "❓ Help",

        "cmd_drive": "Started driving",
        "cmd_work": "Other work",
        "cmd_stop": "Stopped / resting",
        "cmd_status": "How much longer I may drive",
        "cmd_history": "History",
        "cmd_tz": "Time zone",
        "cmd_lang": "Language / Мова",
        "cmd_help": "Help",

        "dur_h": "{h}h",
        "dur_m": "{m}m",
        "dur_hm": "{h}h {m}m",
    },
}

# Кнопки клавіатури -> дія. Обидві мови, щоб стара клавіатура працювала після /lang.
BUTTON_ACTIONS = {
    TEXTS[lang][f"btn_{action}"]: action
    for lang in LANGS
    for action in ("drive", "work", "rest", "status", "history", "help")
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else DEFAULT_LANG
    return TEXTS[lang][key].format(**kwargs)


def lang_from_code(code) -> str:
    """Мова з налаштувань Telegram: англійська, якщо явно не слов'янська."""
    if not code:
        return DEFAULT_LANG
    base = code.split("-")[0].lower()
    return "uk" if base in ("uk", "ru", "be") else "en"


def fmt_duration(lang: str, seconds: int) -> str:
    h, m = divmod(max(int(seconds), 0) // 60, 60)
    if h and m:
        return t(lang, "dur_hm", h=h, m=m)
    if h:
        return t(lang, "dur_h", h=h)
    return t(lang, "dur_m", m=m)


def fmt_time(ts: int, tz, now: int = None) -> str:
    """HH:MM, або dd.mm HH:MM, якщо це інший день, ніж now."""
    d = datetime.fromtimestamp(ts, tz)
    if now is not None and d.date() != datetime.fromtimestamp(now, tz).date():
        return d.strftime("%d.%m %H:%M")
    return d.strftime("%H:%M")
