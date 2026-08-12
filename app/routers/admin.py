from datetime import datetime, timedelta
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin
from ..db import get_db
from ..schemas import InviteCodeCreate, MemberUpdate
from .auth import _generate_code

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _serialize_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "is_disabled": bool(row["is_disabled"]),
        "created_at": row["created_at"],
    }


@router.get("/members")
def list_members(admin=Depends(require_admin), db: Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_serialize_user(r) for r in rows]


@router.patch("/members/{user_id}")
def update_member(user_id: int, payload: MemberUpdate,
                  admin=Depends(require_admin), db: Connection = Depends(get_db)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能停用自己")
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    if payload.is_disabled is not None:
        db.execute("UPDATE users SET is_disabled = ? WHERE id = ?", (int(payload.is_disabled), user_id))
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _serialize_user(row)


@router.get("/invite-codes")
def list_invite_codes(admin=Depends(require_admin), db: Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM invite_codes ORDER BY id DESC LIMIT 100").fetchall()
    return [{
        "code": r["code"],
        "created_at": r["created_at"],
        "used_by": r["used_by"],
        "used_at": r["used_at"],
        "expires_at": r["expires_at"],
    } for r in rows]


@router.post("/invite-codes", status_code=201)
def create_invite_code(payload: InviteCodeCreate,
                       admin=Depends(require_admin), db: Connection = Depends(get_db)):
    code = _generate_code()
    expires_at = None
    if payload.expires_days:
        expires_at = (datetime.utcnow() + timedelta(days=payload.expires_days)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO invite_codes (code, created_by, expires_at) VALUES (?, ?, ?)",
        (code, admin["id"], expires_at),
    )
    return {"code": code, "expires_at": expires_at}
