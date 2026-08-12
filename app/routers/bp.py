from datetime import timedelta
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..dates import combine_local, now_local, parse_date, today_date
from ..db import get_db
from ..schemas import BPCreate, BPUpdate

router = APIRouter(prefix="/api/bp", tags=["blood pressure"])


def _serialize(record) -> dict:
    measured_at = record["measured_at"]  # "YYYY-MM-DD HH:MM:SS"
    return {
        "id": record["id"],
        "measured_at": measured_at[:16].replace(" ", "T"),
        "date": measured_at[:10],
        "time": measured_at[11:16],
        "systolic": record["systolic"],
        "diastolic": record["diastolic"],
        "pulse": record["pulse"],
        "note": record["note"],
    }


def _get_own(db: Connection, user, record_id: int):
    row = db.execute(
        "SELECT * FROM blood_pressure WHERE id = ? AND user_id = ?", (record_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


def _check_values(systolic: int, diastolic: int) -> None:
    if systolic <= diastolic:
        raise HTTPException(status_code=400, detail="收缩压应高于舒张压")


@router.get("")
def list_bp(days: int = Query(90, ge=1, le=365),
            user=Depends(get_current_user), db: Connection = Depends(get_db)):
    since = today_date() - timedelta(days=days - 1)
    since_str = combine_local(since.strftime("%Y-%m-%d"), "00:00").strftime("%Y-%m-%d %H:%M:%S")
    records = db.execute(
        "SELECT * FROM blood_pressure WHERE user_id = ? AND measured_at >= ? ORDER BY measured_at ASC",
        (user["id"], since_str),
    ).fetchall()
    sys_values = [r["systolic"] for r in records]
    dia_values = [r["diastolic"] for r in records]
    count = len(records)
    return {
        "days": days,
        "count": count,
        "avg_systolic": round(sum(sys_values) / count, 1) if count else None,
        "avg_diastolic": round(sum(dia_values) / count, 1) if count else None,
        "records": [_serialize(r) for r in records],
    }


@router.post("", status_code=201)
def create_bp(payload: BPCreate, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _check_values(payload.systolic, payload.diastolic)
    d = parse_date(payload.date)
    if d > today_date():
        raise HTTPException(status_code=400, detail="不能记录未来日期")
    time_str = payload.time or now_local().strftime("%H:%M")
    measured_at = combine_local(payload.date, time_str).strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.execute(
        """INSERT INTO blood_pressure (user_id, measured_at, systolic, diastolic, pulse, note)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user["id"], measured_at, payload.systolic, payload.diastolic, payload.pulse, payload.note),
    )
    row = db.execute("SELECT * FROM blood_pressure WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row)


@router.patch("/{record_id}")
def update_bp(record_id: int, payload: BPUpdate,
              user=Depends(get_current_user), db: Connection = Depends(get_db)):
    record = _get_own(db, user, record_id)
    data = payload.model_dump(exclude_unset=True)
    if "systolic" in data or "diastolic" in data:
        _check_values(
            data.get("systolic", record["systolic"]),
            data.get("diastolic", record["diastolic"]),
        )
    if "date" in data or "time" in data:
        date_str = data.get("date", record["measured_at"][:10])
        time_str = data.get("time", record["measured_at"][11:16])
        if parse_date(date_str) > today_date():
            raise HTTPException(status_code=400, detail="不能记录未来日期")
        new_measured = combine_local(date_str, time_str).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE blood_pressure SET measured_at = ? WHERE id = ?", (new_measured, record_id))
    if "systolic" in data:
        db.execute("UPDATE blood_pressure SET systolic = ? WHERE id = ?", (data["systolic"], record_id))
    if "diastolic" in data:
        db.execute("UPDATE blood_pressure SET diastolic = ? WHERE id = ?", (data["diastolic"], record_id))
    if "pulse" in data:
        db.execute("UPDATE blood_pressure SET pulse = ? WHERE id = ?", (data["pulse"], record_id))
    if "note" in data:
        db.execute("UPDATE blood_pressure SET note = ? WHERE id = ?", (data["note"], record_id))
    row = db.execute("SELECT * FROM blood_pressure WHERE id = ?", (record_id,)).fetchone()
    return _serialize(row)


@router.delete("/{record_id}", status_code=204)
def delete_bp(record_id: int, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _get_own(db, user, record_id)
    db.execute("DELETE FROM blood_pressure WHERE id = ? AND user_id = ?", (record_id, user["id"]))
