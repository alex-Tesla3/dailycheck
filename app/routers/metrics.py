from datetime import timedelta
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..dates import parse_date, today_date, utc_now_str
from ..db import get_db
from ..schemas import MetricCreate, MetricUpdate

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _serialize(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "value": row["value"],
        "unit": row["unit"],
        "date": row["date"],
        "note": row["note"],
    }


def _get_own(db, user, record_id: int):
    row = db.execute(
        "SELECT * FROM metrics WHERE id = ? AND user_id = ?", (record_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


@router.get("")
def list_metrics(days: int = Query(90, ge=1, le=365),
                 user=Depends(get_current_user), db: Connection = Depends(get_db)):
    since = (today_date() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = db.execute(
        "SELECT * FROM metrics WHERE user_id = ? AND date >= ? ORDER BY date, id",
        (user["id"], since),
    ).fetchall()
    latest = {}
    for r in rows:
        latest[r["name"]] = _serialize(r)
    return {
        "days": days,
        "count": len(rows),
        "records": [_serialize(r) for r in rows],
        "latest": latest,
    }


@router.post("", status_code=201)
def create_metric(payload: MetricCreate, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    d = parse_date(payload.date)
    if d > today_date():
        raise HTTPException(status_code=400, detail="不能记录未来日期")
    cursor = db.execute(
        """INSERT INTO metrics (user_id, name, value, unit, date, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user["id"], payload.name, payload.value, payload.unit, payload.date, payload.note, utc_now_str()),
    )
    row = db.execute("SELECT * FROM metrics WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row)


@router.patch("/{record_id}")
def update_metric(record_id: int, payload: MetricUpdate,
                  user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _get_own(db, user, record_id)
    data = payload.model_dump(exclude_unset=True)
    if "date" in data:
        if parse_date(data["date"]) > today_date():
            raise HTTPException(status_code=400, detail="不能记录未来日期")
    fields = {
        "name": data.get("name"),
        "value": data.get("value"),
        "unit": data.get("unit"),
        "date": data.get("date"),
        "note": data.get("note"),
    }
    for col, val in fields.items():
        if col in data:
            db.execute(f"UPDATE metrics SET {col} = ? WHERE id = ?", (val, record_id))
    row = db.execute("SELECT * FROM metrics WHERE id = ?", (record_id,)).fetchone()
    return _serialize(row)


@router.delete("/{record_id}", status_code=204)
def delete_metric(record_id: int, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    _get_own(db, user, record_id)
    db.execute("DELETE FROM metrics WHERE id = ? AND user_id = ?", (record_id, user["id"]))
