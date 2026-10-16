# Ключи намазов и их названия. Порядок важен — в нём показывается статус.
PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

PRAYER_NAMES = {
    "fajr": "Фаджр",
    "dhuhr": "Зухр",
    "asr": "Аср",
    "maghrib": "Магриб",
    "isha": "Иша",
}

# Отдельный счётчик для постов
FAST = "fast"

HELP = (
    "<b>Команды</b>\n\n"
    "/start — регистрация и статус\n"
    "/fajr /dhuhr /asr /maghrib /isha — отметить намаз (+1)\n"
    "   можно сразу несколько: <code>/fajr 10</code>\n"
    "/day — отметить целый день (все намазы +1), <code>/day 5</code> — 5 дней\n"
    "/fast — отметить пост (<code>/fast 5</code> — сразу 5)\n"
    "/fasts — настроить долг по постам\n"
    "/edit — изменить долг по дням (по каждому намазу или всем)\n"
    "   быстро: <code>/edit fajr 1700</code>, <code>/edit all 1825</code>, <code>/edit fast 30</code>\n"
    "/status — текущее положение\n"
    "/reset — сбросить и начать заново"
)


def _fmt_table(rows):
    """Выравнивает пары (подпись, число) в моноширинную таблицу."""
    width_label = max(len(label) for label, _ in rows)
    width_value = max(len(str(value)) for _, value in rows)
    return "\n".join(
        f"{label:<{width_label}}  {str(value):>{width_value}}" for label, value in rows
    )


def build_status(counters: dict) -> str:
    """Собирает текст с остатком долга по намазам и постам.

    counters: {kind: (total, done)}
    """
    rows = []
    total_all = 0
    done_all = 0
    for kind in PRAYERS:
        total, done = counters.get(kind, (0, 0))
        total_all += total
        done_all += done
        rows.append((PRAYER_NAMES[kind], total - done))

    percent = round(done_all / total_all * 100) if total_all else 0
    text = (
        "<b>Осталось наверстать:</b>\n"
        f"<pre>{_fmt_table(rows)}</pre>\n"
        f"Всего: {done_all} из {total_all} ({percent}% готово)"
    )

    fast_total, fast_done = counters.get(FAST, (0, 0))
    if fast_total > 0:
        text += f"\n\n🌙 Посты: осталось {fast_total - fast_done} из {fast_total}"

    return text
