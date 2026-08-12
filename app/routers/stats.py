import calendar
from datetime import date, timedelta
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..dates import today_date, today_str
from ..db import get_db

router = APIRouter(prefix="/api", tags=["stats"])


def _done_dates(db: Connection, user_id: int, habit_id: int) -> set:
    rows = db.execute(
        "SELECT date FROM checkins WHERE user_id = ? AND habit_id = ? AND done = 1",
        (user_id, habit_id),
    ).fetchall()
    return {r["date"] for r in rows}


def _current_streak(done: set) -> int:
    """连续天数：今天完成则从今天起算，否则从昨天起算。"""
    cursor = today_date()
    if today_str() not in done:
        cursor = cursor - timedelta(days=1)
    streak = 0
    while cursor.strftime("%Y-%m-%d") in done:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


@router.get("/stats/month")
def month_stats(year: int = Query(...), month: int = Query(...),
                user=Depends(get_current_user), db: Connection = Depends(get_db)):
    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        raise HTTPException(status_code=400, detail="月份参数无效")
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    today = today_date()
    elapsed = 0
    if today >= first:
        elapsed = (min(today, last) - first).days + 1

    habits = db.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY sort_order, id", (user["id"],)
    ).fetchall()
    result = []
    for h in habits:
        rows = db.execute(
            """SELECT date FROM checkins
               WHERE user_id = ? AND habit_id = ? AND done = 1
                 AND date >= ? AND date <= ?""",
            (user["id"], h["id"], first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")),
        ).fetchall()
        days = {r["date"]: True for r in rows}
        done_count = len(rows)
        rate = round(done_count / elapsed, 2) if elapsed else 0.0
        result.append({
            "id": h["id"],
            "name": h["name"],
            "color": h["color"],
            "days": days,
            "done_count": done_count,
            "elapsed_days": elapsed,
            "rate": rate,
            "streak": _current_streak(_done_dates(db, user["id"], h["id"])),
        })
    return {"year": year, "month": month, "today": today_str(), "habits": result}


@router.get("/habits/{habit_id}/streak")
def habit_streak(habit_id: int, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return {"streak": _current_streak(_done_dates(db, user["id"], habit_id))}
