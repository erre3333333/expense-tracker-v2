import os
import aiosqlite
from contextlib import asynccontextmanager

DB_PATH = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DATABASE_PATH = os.path.join(DB_PATH, "expenses.db")

_create_users_sql = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_create_transactions_sql = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT DEFAULT '',
    date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@asynccontextmanager
async def _connect():
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


get_db = _connect


async def init_db():
    os.makedirs(DB_PATH, exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(_create_users_sql)
        await db.execute(_create_transactions_sql)
        await db.commit()
