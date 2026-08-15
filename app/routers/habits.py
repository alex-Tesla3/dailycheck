from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..dates import utc_now_str
from ..db import get_db
from ..schemas import HabitCreate, HabitUpdate

router = APIRouter(prefix="/api/habits", tags=["habits"])

HABIT_COLS = "id, name, value_label, reminder_time, reminder_enabled, color, sort_order"


def _get_own(db: Connection, user, habit_id: int):
    row = db.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return row


def _serialize(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "value_label": row["value_label"],
        "reminder_time": row["reminder_time"],
        "reminder_enabled": bool(row["reminder_enabled"]),
        "color": row["color"],
        "sort_order": row["sort_order"],
    }


@router.get("")
def list_habits(user=Depends(get_current_user), db: Connection = Depends(get_db)):
    rows = db.execute(
        f"SELECT {HABIT_COLS} FROM habits WHERE user_id = ? ORDER BY sort_order, id",
        (user["id"],),
    ).fetchall()
    return [_serialize(r) for r in rows]


@router.post("", status_code=201)
def create_habit(payload: HabitCreate, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    cursor = db.execute(
        """INSERT INTO habits (user_id, name, value_label, reminder_time, reminder_enabled, color, sort_order, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user["id"], payload.name, payload.value_label, payload.reminder_time,
         int(payload.reminder_enabled), payload.color, payload.sort_order, utc_now_str()),
    )
    row = db.execute(f"SELECT {HABIT_COLS} FROM habits WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row)


@router.patch("/{habit_id}")
def update_habit(habit_id: int, payload: HabitUpdate,
                 user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _get_own(db, user, habit_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        db.execute("UPDATE habits SET name = ? WHERE id = ? AND user_id = ?", (data["name"], habit_id, user["id"]))
    if "value_label" in data:
        db.execute("UPDATE habits SET value_label = ? WHERE id = ? AND user_id = ?", (data["value_label"], habit_id, user["id"]))
    if "reminder_time" in data:
        db.execute("UPDATE habits SET reminder_time = ? WHERE id = ? AND user_id = ?", (data["reminder_time"], habit_id, user["id"]))
    if "reminder_enabled" in data:
        db.execute("UPDATE habits SET reminder_enabled = ? WHERE id = ? AND user_id = ?", (int(data["reminder_enabled"]), habit_id, user["id"]))
    if "color" in data:
        db.execute("UPDATE habits SET color = ? WHERE id = ? AND user_id = ?", (data["color"], habit_id, user["id"]))
    if "sort_order" in data:
        db.execute("UPDATE habits SET sort_order = ? WHERE id = ? AND user_id = ?", (data["sort_order"], habit_id, user["id"]))
    row = db.execute(f"SELECT {HABIT_COLS} FROM habits WHERE id = ?", (habit_id,)).fetchone()
    return _serialize(row)


@router.delete("/{habit_id}", status_code=204)
def delete_habit(habit_id: int, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _get_own(db, user, habit_id)
    db.execute("DELETE FROM habits WHERE id = ? AND user_id = ?", (habit_id, user["id"]))
