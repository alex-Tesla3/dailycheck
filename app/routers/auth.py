import secrets
import string
from datetime import datetime
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_current_user, hash_password, verify_password
from ..dates import utc_now_str
from ..db import get_db
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..seed import ensure_default_habits

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _consume_invite_code(db: Connection, code: str, user_id: int) -> None:
    row = db.execute("SELECT * FROM invite_codes WHERE code = ?", (code,)).fetchone()
    if not row or row["used_by"] is not None:
        raise HTTPException(status_code=400, detail="邀请码无效或已被使用")
    if row["expires_at"] is not None and row["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"):
        raise HTTPException(status_code=400, detail="邀请码已过期")
    db.execute(
        "UPDATE invite_codes SET used_by = ?, used_at = ? WHERE id = ?",
        (user_id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
    )


def _user_out(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "is_disabled": bool(row["is_disabled"]),
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Connection = Depends(get_db)):
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count == 0:
        # 首个用户自动成为管理员，无需邀请码
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
            (payload.username, hash_password(payload.password), utc_now_str()),
        )
        user_id = cursor.lastrowid
        ensure_default_habits(db, user_id)
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_out(row)

    if not payload.invite_code:
        raise HTTPException(status_code=400, detail="需要邀请码")
    if db.execute("SELECT 1 FROM users WHERE username = ?", (payload.username,)).fetchone():
        raise HTTPException(status_code=400, detail="用户名已存在")

    cursor = db.execute(
        "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 0, ?)",
        (payload.username, hash_password(payload.password), utc_now_str()),
    )
    user_id = cursor.lastrowid
    _consume_invite_code(db, payload.invite_code, user_id)
    ensure_default_habits(db, user_id)
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_out(row)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE username = ?", (payload.username,)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if row["is_disabled"]:
        raise HTTPException(status_code=403, detail="账号已被停用")
    request.session["user_id"] = row["id"]
    return _user_out(row)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return _user_out(user)
