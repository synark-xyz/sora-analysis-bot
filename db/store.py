import sqlite3
import os
import json
from datetime import datetime, timezone


DB_PATH = os.environ.get("DB_PATH", "sora.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _dict_from_row(cursor, row):
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def init_db():
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL CHECK(market IN ('us', 'crypto')),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                verdict TEXT NOT NULL CHECK(verdict IN ('BUY', 'SELL', 'HOLD')),
                confidence REAL,
                entry_low REAL,
                entry_high REAL,
                exit_target REAL,
                stop_loss REAL,
                rr_ratio REAL,
                reason TEXT,
                strategy TEXT,
                regime TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signal_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                actual_return_3d REAL,
                actual_return_7d REAL,
                actual_return_14d REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('took', 'skip', 'partial')),
                reason TEXT,
                emotional_state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER DEFAULT 1 PRIMARY KEY,
                profile_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_type TEXT,
                symbol TEXT,
                pattern TEXT,
                confidence_impact REAL DEFAULT 0,
                applied_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS llm_cache (
                input_hash TEXT PRIMARY KEY,
                output TEXT NOT NULL,
                model TEXT NOT NULL,
                cached_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                entry_price REAL NOT NULL,
                qty REAL,
                stop_loss REAL,
                take_profit REAL,
                signal_id INTEGER,
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                close_reason TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            );

            CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
            CREATE INDEX IF NOT EXISTS idx_lessons_type ON agent_lessons(lesson_type);
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        """)
        conn.commit()
    finally:
        conn.close()


def add_watchlist_symbol(symbol, market="us"):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO watchlist (symbol, market, added_at) VALUES (?, ?, datetime('now'))",
            (symbol.upper(), market),
        )
        conn.commit()
        return {"symbol": symbol.upper(), "market": market, "status": "added"}
    finally:
        conn.close()


def remove_watchlist_symbol(symbol):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.upper(),))
        deleted = c.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def get_watchlist():
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT symbol, market, added_at FROM watchlist ORDER BY added_at DESC")
        return [dict(zip([desc[0] for desc in c.description], row)) for row in c.fetchall()]
    finally:
        conn.close()


def save_signal(signal_data):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO signals (symbol, market, verdict, confidence, entry_low, entry_high,
               exit_target, stop_loss, rr_ratio, reason, strategy, regime)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal_data.get("symbol", "").upper(),
                signal_data.get("market", "us"),
                signal_data.get("verdict", "HOLD"),
                signal_data.get("confidence"),
                signal_data.get("entry_low"),
                signal_data.get("entry_high"),
                signal_data.get("exit_target"),
                signal_data.get("stop_loss"),
                signal_data.get("rr_ratio"),
                signal_data.get("reason"),
                signal_data.get("strategy"),
                signal_data.get("regime"),
            ),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_signals(days=7, limit=50):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """SELECT * FROM signals WHERE created_at >= datetime('now', ? || ' days')
               ORDER BY created_at DESC LIMIT ?""",
            (f"-{days}", limit),
        )
        cols = [desc[0] for desc in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        conn.close()


def save_signal_outcome(signal_id, return_3d=None, return_7d=None, return_14d=None):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO signal_outcomes (signal_id, actual_return_3d, actual_return_7d, actual_return_14d)
               VALUES (?, ?, ?, ?)""",
            (signal_id, return_3d, return_7d, return_14d),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def save_feedback(symbol, action, reason=None, emotional_state=None):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO user_feedback (symbol, action, reason, emotional_state)
               VALUES (?, ?, ?, ?)""",
            (symbol.upper(), action, reason, emotional_state),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_profile():
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT profile_json, updated_at FROM user_profile WHERE id = 1")
        row = c.fetchone()
        if row:
            return json.loads(row[0])
        return {}
    finally:
        conn.close()


def save_profile(profile_json):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO user_profile (id, profile_json, updated_at)
               VALUES (1, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
               profile_json = excluded.profile_json,
               updated_at = datetime('now')""",
            (json.dumps(profile_json),),
        )
        conn.commit()
    finally:
        conn.close()


def save_lesson(lesson_type, symbol, pattern, confidence_impact=0):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO agent_lessons (lesson_type, symbol, pattern, confidence_impact)
               VALUES (?, ?, ?, ?)""",
            (lesson_type, symbol.upper(), pattern, confidence_impact),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_lessons(limit=20):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM agent_lessons ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        cols = [desc[0] for desc in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        conn.close()


def cache_llm_get(input_hash, model):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT output FROM llm_cache WHERE input_hash = ? AND model = ? AND expires_at > datetime('now')",
            (input_hash, model),
        )
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def add_position(symbol, market, entry_price, qty=None, stop_loss=None, take_profit=None, signal_id=None):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO positions (symbol, market, entry_price, qty, stop_loss, take_profit, signal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (symbol.upper(), market, entry_price, qty, stop_loss, take_profit, signal_id),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_open_positions():
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY taken_at DESC")
        cols = [desc[0] for desc in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        conn.close()


def close_position(symbol, close_reason="manual"):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """UPDATE positions SET status = 'closed', closed_at = datetime('now'), close_reason = ?
               WHERE symbol = ? AND status = 'open'""",
            (close_reason, symbol.upper()),
        )
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def cache_llm_set(input_hash, model, output):
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO llm_cache (input_hash, output, model, cached_at, expires_at)
               VALUES (?, ?, ?, datetime('now'), datetime('now', '+4 hours'))""",
            (input_hash, output, model),
        )
        conn.commit()
    finally:
        conn.close()
