import json
from datetime import datetime, timezone

import aiosqlite

from .config import settings
from .texts import PRAYERS

INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    years      REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS counters (
    user_id INTEGER NOT NULL,
    kind    TEXT    NOT NULL,
    total   INTEGER NOT NULL DEFAULT 0,
    done    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, kind)
);

-- Последнее действие пользователя для отмены (/undo).
-- changes: JSON {kind: сколько зачтено}, например {"fajr": 1} или {"fajr": 5, "dhuhr": 5}
CREATE TABLE IF NOT EXISTS last_action (
    user_id INTEGER PRIMARY KEY,
    changes TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(INIT_SQL)
        await db.commit()


async def is_registered(user_id: int) -> bool:
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None


async def _upsert_user(db: aiosqlite.Connection, user_id: int, years) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO users (user_id, years, created_at) VALUES (?, ?, ?)",
        (user_id, years, datetime.now(timezone.utc).isoformat()),
    )


async def register_all(user_id: int, days: int, years=None) -> None:
    """Регистрация: одинаковый долг (в днях) по каждому из 5 намазов."""
    async with aiosqlite.connect(settings.db_path) as db:
        await _upsert_user(db, user_id, years)
        for kind in PRAYERS:
            await db.execute(
                "INSERT OR REPLACE INTO counters (user_id, kind, total, done) "
                "VALUES (?, ?, ?, 0)",
                (user_id, kind, days),
            )
        await db.execute("DELETE FROM last_action WHERE user_id = ?", (user_id,))
        await db.commit()


async def register_each(user_id: int, totals: dict) -> None:
    """Регистрация: свой долг (в днях) для каждого намаза."""
    async with aiosqlite.connect(settings.db_path) as db:
        await _upsert_user(db, user_id, None)
        for kind in PRAYERS:
            await db.execute(
                "INSERT OR REPLACE INTO counters (user_id, kind, total, done) "
                "VALUES (?, ?, ?, 0)",
                (user_id, kind, int(totals.get(kind, 0))),
            )
        await db.execute("DELETE FROM last_action WHERE user_id = ?", (user_id,))
        await db.commit()


async def set_total(user_id: int, kind: str, total: int) -> None:
    """Задаёт/меняет долг (total) для счётчика. Прогресс (done) сохраняется
    и подрезается до нового total, чтобы остаток не уходил в минус."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT done FROM counters WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        )
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO counters (user_id, kind, total, done) VALUES (?, ?, ?, 0)",
                (user_id, kind, total),
            )
        else:
            done = min(row[0], total)
            await db.execute(
                "UPDATE counters SET total = ?, done = ? WHERE user_id = ? AND kind = ?",
                (total, done, user_id, kind),
            )
        await db.commit()


async def add_done(user_id: int, kind: str, n: int) -> int:
    """Отмечает n наверстанных единиц. Возвращает реально зачтённое число
    (не больше оставшегося долга)."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT total, done FROM counters WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        )
        row = await cur.fetchone()
        if row is None:
            return 0
        total, done = row
        new_done = min(total, done + n)
        added = new_done - done
        if added:
            await db.execute(
                "UPDATE counters SET done = ? WHERE user_id = ? AND kind = ?",
                (new_done, user_id, kind),
            )
            await db.commit()
        return added


async def undo_done(user_id: int, kind: str, n: int) -> int:
    """Откатывает n зачтённых единиц (done уменьшается, но не ниже 0).
    Возвращает фактически откатанное число."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT done FROM counters WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        )
        row = await cur.fetchone()
        if row is None:
            return 0
        done = row[0]
        new_done = max(0, done - n)
        removed = done - new_done
        if removed:
            await db.execute(
                "UPDATE counters SET done = ? WHERE user_id = ? AND kind = ?",
                (new_done, user_id, kind),
            )
            await db.commit()
        return removed


async def record_action(user_id: int, changes: dict) -> None:
    """Запоминает последнее действие (для /undo). Пустое — очищает."""
    async with aiosqlite.connect(settings.db_path) as db:
        if changes:
            await db.execute(
                "INSERT OR REPLACE INTO last_action (user_id, changes) VALUES (?, ?)",
                (user_id, json.dumps(changes)),
            )
        else:
            await db.execute("DELETE FROM last_action WHERE user_id = ?", (user_id,))
        await db.commit()


async def pop_action(user_id: int):
    """Возвращает и удаляет последнее действие ({kind: n}) или None."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT changes FROM last_action WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if row is None:
            return None
        await db.execute("DELETE FROM last_action WHERE user_id = ?", (user_id,))
        await db.commit()
        return json.loads(row[0])


async def get_counters(user_id: int) -> dict:
    """Возвращает {kind: (total, done)}."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT kind, total, done FROM counters WHERE user_id = ?", (user_id,)
        )
        rows = await cur.fetchall()
    return {kind: (total, done) for kind, total, done in rows}


async def reset_user(user_id: int) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("DELETE FROM counters WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM last_action WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
