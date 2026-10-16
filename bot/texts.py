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
    "/undo — отменить последнюю отметку (или кнопкой «↩️ Отменить»)\n"
    "/fasts — настроить долг по постам\n"
    "/edit — изменить долг по дням (по каждому намазу или всем)\n"
    "   быстро: <code>/edit fajr 1700</code>, <code>/edit all 1825</code>, <code>/edit fast 30</code>\n"
    "/status — текущее положение\n"
    "/reset — сбросить и начать заново"
)


def _fmt_progress(rows):
    """Моноширинная таблица 'подпись  наверстано / всего'."""
    width_label = max(len(label) for label, _, _ in rows)
    width_done = max(len(str(done)) for _, done, _ in rows)
    width_total = max(len(str(total)) for _, _, total in rows)
    return "\n".join(
        f"{label:<{width_label}}  {done:>{width_done}} / {total:>{width_total}}"
        for label, done, total in rows
    )


def build_status(counters: dict) -> str:
    """Собирает текст с прогрессом (наверстано / всего) по намазам и постам.

    counters: {kind: (total, done)}
    """
    rows = []
    total_all = 0
    done_all = 0
    for kind in PRAYERS:
        total, done = counters.get(kind, (0, 0))
        total_all += total
        done_all += done
        rows.append((PRAYER_NAMES[kind], done, total))

    percent = round(done_all / total_all * 100) if total_all else 0
    text = (
        "<b>Наверстано / всего:</b>\n"
        f"<pre>{_fmt_progress(rows)}</pre>\n"
        f"Всего: {done_all} / {total_all} ({percent}%)"
    )

    fast_total, fast_done = counters.get(FAST, (0, 0))
    if fast_total > 0:
        text += f"\n\n🌙 Посты: {fast_done} / {fast_total}"

    return text
