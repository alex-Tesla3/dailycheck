"""数据层：同时支持 SQLite（本地/默认）与 PostgreSQL（Supabase 等）。
- 通过 DATABASE_URL 自动选择：sqlite:///... 或 postgresql://...
- SQL 统一使用 ? 占位符；Postgres 端自动翻译为 %s，INSERT 自动加 RETURNING id
- 时间戳一律由 Python 生成（YYYY-MM-DD HH:MM:SS），跨库一致
"""
import sqlite3
from typing import Iterator

from .config import DATABASE_URL


def _is_postgres(url: str) -> bool:
    return url.startswith("postgres") or url.startswith("postgresql")


def _translate(sql: str) -> str:
    return sql.replace("?", "%s")


class Cursor:
    """统一游标：兼容 sqlite3.Cursor 与 psycopg2 cursor。"""

    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self._lastrowid = lastrowid

    @property
    def lastrowid(self):
        return self._lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)


class Database:
    def __init__(self):
        self.is_postgres = _is_postgres(DATABASE_URL)
        self._raw = self._connect()
        self._lastrowid = None

    def _connect(self):
        if self.is_postgres:
            import psycopg2  # 仅在 Postgres 时按需导入
            from psycopg2.extras import RealDictCursor

            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn = sqlite3.connect(self._sqlite_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _sqlite_path(self) -> str:
        # sqlite:///path
        return DATABASE_URL.replace("sqlite:///", "", 1)

    def execute(self, sql: str, params=()):
        self._lastrowid = None
        if self.is_postgres:
            stmt = _translate(sql)
            cur = self._raw.cursor()
            if stmt.lstrip().upper().startswith("INSERT") and " RETURNING " not in stmt.upper():
                stmt += " RETURNING id"
                cur.execute(stmt, params)
                row = cur.fetchone()
                self._lastrowid = row["id"] if row else None
            else:
                cur.execute(stmt, params)
            return Cursor(cur, self._lastrowid)
        cur = self._raw.execute(sql, params)
        return Cursor(cur, cur.lastrowid)

    def executemany(self, sql: str, seq_of_params):
        stmt = _translate(sql) if self.is_postgres else sql
        cur = self._raw.cursor()
        cur.executemany(stmt, seq_of_params)
        return Cursor(cur)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _schema_statements(is_postgres: bool) -> list:
    id_type = "BIGSERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ref_type = "BIGINT" if is_postgres else "INTEGER"
    return [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {id_type} NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_disabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS invite_codes (
            id {id_type} NOT NULL,
            code TEXT NOT NULL UNIQUE,
            created_by {ref_type},
            created_at TEXT NOT NULL,
            used_by {ref_type},
            used_at TEXT,
            expires_at TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS habits (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value_label TEXT,
            reminder_time TEXT,
            reminder_enabled INTEGER NOT NULL DEFAULT 0,
            color TEXT NOT NULL DEFAULT '#4f8cff',
            sort_order INTEGER NOT NULL DEFAULT 0,
            last_reminder_date TEXT,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS checkins (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            habit_id {ref_type} NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            value TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (user_id, habit_id, date)
        )""",
        f"""CREATE TABLE IF NOT EXISTS push_subscriptions (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS blood_pressure (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            measured_at TEXT NOT NULL,
            systolic INTEGER NOT NULL,
            diastolic INTEGER NOT NULL,
            pulse INTEGER,
            note TEXT,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS metrics (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            date TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS analyses (
            id {id_type} NOT NULL,
            user_id {ref_type} NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start TEXT,
            period_end TEXT,
            content TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_checkins_user_date ON checkins(user_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_checkins_habit_date ON checkins(habit_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_bp_user_time ON blood_pressure(user_id, measured_at)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_user_date ON metrics(user_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id)",
    ]


def init_db() -> None:
    db = Database()
    try:
        for stmt in _schema_statements(db.is_postgres):
            db.execute(stmt)
        db.commit()
    finally:
        db.close()


def get_db() -> Iterator[Database]:
    """FastAPI 依赖：每个请求一个连接，请求结束提交。"""
    db = Database()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
