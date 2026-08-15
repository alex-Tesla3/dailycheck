from sqlite3 import Connection

DEFAULT_HABITS = [
    ("锻炼", "分钟", "#4f8cff", 0),
    ("吃药", "次", "#ff6b6b", 1),
]


def ensure_default_habits(conn, user_id: int) -> None:
    """用户首次登录时预置示例习惯。"""
    from .dates import utc_now_str

    count = conn.execute(
        "SELECT COUNT(*) FROM habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    if count == 0:
        now = utc_now_str()
        conn.executemany(
            "INSERT INTO habits (user_id, name, value_label, color, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(user_id, name, label, color, sort_order, now) for name, label, color, sort_order in DEFAULT_HABITS],
        )
