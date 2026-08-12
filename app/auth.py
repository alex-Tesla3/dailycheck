import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlite3 import Row

from .db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def get_current_user(request: Request, db=Depends(get_db)) -> Row:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or row["is_disabled"]:
        raise HTTPException(status_code=401, detail="账号不可用")
    return row


def require_admin(user: Row = Depends(get_current_user)) -> Row:
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
