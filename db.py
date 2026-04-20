import aiosqlite
import logging

DB_PATH = 'users.db'


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                last_name     TEXT,
                language_code TEXT,
                photo_file_id TEXT,
                is_blocked    INTEGER DEFAULT 0,
                last_seen     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS searches (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                kod        TEXT NOT NULL,
                found      INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        await db.commit()


async def upsert_user(user) -> bool:
    """Returns True if it is a new user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id FROM users WHERE user_id = ?', (user.id,)
        ) as c:
            exists = await c.fetchone()

        if exists:
            await db.execute('''
                UPDATE users
                SET username=?, first_name=?, last_name=?,
                    language_code=?, last_seen=CURRENT_TIMESTAMP, is_blocked=0
                WHERE user_id=?
            ''', (user.username, user.first_name, user.last_name,
                  user.language_code, user.id))
        else:
            await db.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, language_code)
                VALUES (?, ?, ?, ?, ?)
            ''', (user.id, user.username, user.first_name,
                  user.last_name, user.language_code))

        await db.commit()
        return not bool(exists)


async def save_photo(user_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET photo_file_id=? WHERE user_id=?', (file_id, user_id)
        )
        await db.commit()


async def mark_blocked(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET is_blocked=1 WHERE user_id=?', (user_id,)
        )
        await db.commit()


async def log_search(user_id: int, kod: str, found: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO searches (user_id, kod, found) VALUES (?, ?, ?)',
            (user_id, kod, 1 if found else 0)
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM users WHERE user_id=?', (user_id,)
        ) as c:
            return await c.fetchone()


async def get_user_history(user_id: int, limit: int = 15):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT kod, found, created_at FROM searches
               WHERE user_id=? ORDER BY created_at DESC LIMIT ?''',
            (user_id, limit)
        ) as c:
            return await c.fetchall()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = {}

        for key, sql in [
            ('total',          'SELECT COUNT(*) as n FROM users'),
            ('alive',          "SELECT COUNT(*) as n FROM users WHERE is_blocked=0 AND last_seen>=datetime('now','-30 days')"),
            ('dead',           "SELECT COUNT(*) as n FROM users WHERE is_blocked=0 AND last_seen<datetime('now','-30 days')"),
            ('blocked',        'SELECT COUNT(*) as n FROM users WHERE is_blocked=1'),
            ('new_today',      "SELECT COUNT(*) as n FROM users WHERE created_at>=datetime('now','start of day')"),
            ('new_7d',         "SELECT COUNT(*) as n FROM users WHERE created_at>=datetime('now','-7 days')"),
            ('new_30d',        "SELECT COUNT(*) as n FROM users WHERE created_at>=datetime('now','-30 days')"),
            ('searching',      "SELECT COUNT(*) as n FROM users WHERE last_seen>=datetime('now','-5 minutes')"),
            ('active_24h',     "SELECT COUNT(*) as n FROM users WHERE last_seen>=datetime('now','-1 day')"),
            ('searches_today', "SELECT COUNT(*) as n FROM searches WHERE created_at>=datetime('now','start of day')"),
            ('searches_7d',    "SELECT COUNT(*) as n FROM searches WHERE created_at>=datetime('now','-7 days')"),
            ('total_searches', 'SELECT COUNT(*) as n FROM searches'),
        ]:
            async with db.execute(sql) as c:
                s[key] = (await c.fetchone())['n']

        async with db.execute(
            'SELECT language_code, COUNT(*) as cnt FROM users GROUP BY language_code ORDER BY cnt DESC'
        ) as c:
            s['langs'] = await c.fetchall()

        s['avg_searches'] = (
            round(s['total_searches'] / s['total'], 1) if s['total'] else 0
        )
        return s
