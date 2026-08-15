from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..dates import parse_date, today_date, utc_now_str
from ..db import get_db
from ..schemas import CheckinUpsert

router = APIRouter(prefix="/api", tags=["checkins"])


def _get_own(db: Connection, user, habit_id: int):
    row = db.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return row


@router.get("/today")
def today(date: str = Query(..., description="YYYY-MM-DD"),
          user=Depends(get_current_user), db: Connection = Depends(get_db)):
    d = parse_date(date)
    if d > today_date():
        raise HTTPException(status_code=400, detail="不能查看未来日期")
    habits = db.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY sort_order, id", (user["id"],)
    ).fetchall()
    checkins = {
        r["habit_id"]: r
        for r in db.execute(
            "SELECT * FROM checkins WHERE user_id = ? AND date = ?", (user["id"], date)
        ).fetchall()
    }
    result = []
    for h in habits:
        c = checkins.get(h["id"])
        result.append({
            "id": h["id"],
            "name": h["name"],
            "value_label": h["value_label"],
            "reminder_time": h["reminder_time"],
            "reminder_enabled": bool(h["reminder_enabled"]),
            "color": h["color"],
            "checkin": None if c is None else {
                "done": bool(c["done"]), "value": c["value"], "note": c["note"],
            },
        })
    return {"date": date, "habits": result}


@router.get("/checkins")
def list_checkins(date: str = Query(..., description="YYYY-MM-DD"),
                  user=Depends(get_current_user), db: Connection = Depends(get_db)):
    parse_date(date)
    rows = db.execute(
        "SELECT * FROM checkins WHERE user_id = ? AND date = ?", (user["id"], date)
    ).fetchall()
    return [{"habit_id": r["habit_id"], "done": bool(r["done"]), "value": r["value"], "note": r["note"]} for r in rows]


@router.put("/checkins/{habit_id}")
def upsert_checkin(habit_id: int, payload: CheckinUpsert,
                   date: str = Query(..., description="YYYY-MM-DD"),
                   user=Depends(get_current_user), db: Connection = Depends(get_db)):
    d = parse_date(date)
    if d > today_date():
        raise HTTPException(status_code=400, detail="不能打卡未来日期")
    _get_own(db, user, habit_id)
    row = db.execute(
        "SELECT * FROM checkins WHERE user_id = ? AND habit_id = ? AND date = ?",
        (user["id"], habit_id, date),
    ).fetchone()
    now = utc_now_str()
    if row is None:
        db.execute(
            "INSERT INTO checkins (user_id, habit_id, date, done, value, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user["id"], habit_id, date, int(payload.done), payload.value, payload.note, now, now),
        )
    else:
        db.execute(
            "UPDATE checkins SET done = ?, value = ?, note = ?, updated_at = ? WHERE id = ?",
            (int(payload.done), payload.value, payload.note, now, row["id"]),
        )
    return {"habit_id": habit_id, "done": payload.done, "value": payload.value, "note": payload.note}
