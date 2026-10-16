from datetime import datetime, timezone

import aiosqlite

from .config import settings
from .texts import PRAYERS, FAST

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
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(INIT_SQL)
        await db.commit()


async def is_registered(user_id: int) -> bool:
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None


async def register_user(user_id: int, years: float) -> int:
    """Создаёт пользователя и счётчики намазов. Возвращает число дней долга."""
    days = max(0, round(years * settings.days_per_year))
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, years, created_at) VALUES (?, ?, ?)",
            (user_id, years, datetime.now(timezone.utc).isoformat()),
        )
        for kind in PRAYERS:
            await db.execute(
                "INSERT OR REPLACE INTO counters (user_id, kind, total, done) "
                "VALUES (?, ?, ?, 0)",
                (user_id, kind, days),
            )
        await db.commit()
    return days


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


async def set_fast(user_id: int, days: int) -> None:
    """Задаёт долг по постам. Прогресс (done) сохраняется и не превышает новый total."""
    async with aiosqlite.connect(settings.db_path) as db:
        cur = await db.execute(
            "SELECT done FROM counters WHERE user_id = ? AND kind = ?",
            (user_id, FAST),
        )
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO counters (user_id, kind, total, done) VALUES (?, ?, ?, 0)",
                (user_id, FAST, days),
            )
        else:
            done = min(row[0], days)
            await db.execute(
                "UPDATE counters SET total = ?, done = ? WHERE user_id = ? AND kind = ?",
                (days, done, user_id, FAST),
            )
        await db.commit()


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
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
