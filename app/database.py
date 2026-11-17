"""Async SQLite data layer."""

import aiosqlite
import random
from datetime import datetime, timedelta

from app.config import settings

# ... existing ...

SEED_ITEMS = [
    (730, "AK-47 | Redline (Field-Tested)", 2500.0),
    (730, "AWP | Asiimov (Field-Tested)", 9000.0),
    (730, "Recoil Case", 30.0),
    (570, "Fractal Horns of Inner Abysm", 15000.0),
    (252490, "Metal Facemask", 1500.0),
]


async def seed_if_empty() -> None:
    items = await list_items()
    if items:
        return
    db = await get_db()
    try:
        for appid, name, base in SEED_ITEMS:
            cur = await db.execute(
                "INSERT OR IGNORE INTO items (appid, market_hash_name) VALUES (?, ?)",
                (appid, name),
            )
            await db.commit()
            if cur.lastrowid:
                item_id = cur.lastrowid
            else:
                c = await db.execute(
                    "SELECT id FROM items WHERE appid=? AND market_hash_name=?",
                    (appid, name),
                )
                row = await c.fetchone()
                item_id = row["id"]
            # generate 7 days of history
            now = datetime.utcnow()
            for d in range(7, 0, -1):
                for _ in range(random.randint(1, 2)):
                    captured = now - timedelta(days=d, hours=random.randint(0, 20))
                    lowest = round(base * random.uniform(0.97, 1.03), 2)
                    highest = round(lowest * random.uniform(0.88, 0.95), 2)
                    median = round(lowest * random.uniform(1.0, 1.03), 2)
                    volume = random.randint(5, 200)
                    await db.execute(
                        """INSERT INTO price_snapshots
                           (item_id, lowest_sell, highest_buy, volume_24h, median_price, captured_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (item_id, lowest, highest, volume, median, captured.strftime("%Y-%m-%d %H:%M:%S")),
                    )
            await db.commit()
    finally:
        await db.close()

DB_PATH = settings.db_path

CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appid INTEGER NOT NULL,
    market_hash_name TEXT NOT NULL,
    item_nameid INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(appid, market_hash_name)
);
"""

CREATE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    lowest_sell REAL,
    highest_buy REAL,
    volume_24h INTEGER,
    median_price REAL,
    raw_json TEXT,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);
"""

CREATE_PORTFOLIO = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    buy_price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    bought_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);
"""

CREATE_LOGS = """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_item ON price_snapshots(item_id);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_captured ON price_snapshots(captured_at);",
]


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute(CREATE_ITEMS)
        await db.execute(CREATE_SNAPSHOTS)
        await db.execute(CREATE_PORTFOLIO)
        await db.execute(CREATE_LOGS)
        for q in CREATE_INDEXES:
            await db.execute(q)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    return db


# ---- Items ----

async def add_item(appid: int, market_hash_name: str) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            "INSERT OR IGNORE INTO items (appid, market_hash_name) VALUES (?, ?)",
            (appid, market_hash_name),
        )
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        cur = await db.execute(
            "SELECT id FROM items WHERE appid=? AND market_hash_name=?",
            (appid, market_hash_name),
        )
        row = await cur.fetchone()
        return row["id"]
    finally:
        await db.close()


async def get_item(item_id: int) -> dict | None:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM items WHERE id=?", (item_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_item_by_name(appid: int, market_hash_name: str) -> dict | None:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM items WHERE appid=? AND market_hash_name=?",
            (appid, market_hash_name),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_items() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM items WHERE enabled=1 ORDER BY id DESC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def delete_item(item_id: int) -> None:
    db = await get_db()
    try:
        await db.execute("DELETE FROM items WHERE id=?", (item_id,))
        await db.commit()
    finally:
        await db.close()


async def set_item_nameid(item_id: int, item_nameid: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE items SET item_nameid=? WHERE id=?", (item_nameid, item_id)
        )
        await db.commit()
    finally:
        await db.close()


# ---- Snapshots ----

async def add_snapshot(
    item_id: int,
    lowest_sell: float | None,
    highest_buy: float | None,
    volume_24h: int | None,
    median_price: float | None,
    raw_json: str | None = None,
) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            """INSERT INTO price_snapshots
               (item_id, lowest_sell, highest_buy, volume_24h, median_price, raw_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item_id, lowest_sell, highest_buy, volume_24h, median_price, raw_json),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def latest_snapshot(item_id: int) -> dict | None:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM price_snapshots WHERE item_id=? ORDER BY id DESC LIMIT 1",
            (item_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def snapshot_history(item_id: int, limit: int = 200) -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM price_snapshots WHERE item_id=?
               ORDER BY id ASC LIMIT ?""",
            (item_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ---- Portfolio ----

async def add_portfolio(item_id: int, buy_price: float, quantity: int, note: str | None = None) -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            "INSERT INTO portfolio (item_id, buy_price, quantity, note) VALUES (?, ?, ?, ?)",
            (item_id, buy_price, quantity, note),
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def list_portfolio() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT p.*, i.appid, i.market_hash_name, i.item_nameid
               FROM portfolio p JOIN items i ON i.id=p.item_id
               ORDER BY p.id DESC"""
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def delete_portfolio(entry_id: int) -> None:
    db = await get_db()
    try:
        await db.execute("DELETE FROM portfolio WHERE id=?", (entry_id,))
        await db.commit()
    finally:
        await db.close()


async def add_log(level: str, message: str) -> None:
    db = await get_db()
    try:
        await db.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, message))
        await db.commit()
    finally:
        await db.close()


async def update_portfolio(entry_id: int, buy_price: float | None = None, quantity: int | None = None, note: str | None = None) -> None:
    db = await get_db()
    try:
        fields = []
        vals = []
        if buy_price is not None:
            fields.append("buy_price=?")
            vals.append(buy_price)
        if quantity is not None:
            fields.append("quantity=?")
            vals.append(quantity)
        if note is not None:
            fields.append("note=?")
            vals.append(note)
        if not fields:
            return
        vals.append(entry_id)
        await db.execute(f"UPDATE portfolio SET {', '.join(fields)} WHERE id=?", vals)
        await db.commit()
    finally:
        await db.close()
