"""用户 AI 设置：每个用户可配置自己的 API Key/Base URL/模型，替代共享额度。"""
from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..config import AI_FREE_LIMIT, AI_BASE_URL, AI_MODEL, AI_API_KEY
from ..db import get_db
from ..schemas import AIUpdate

router = APIRouter(prefix="/api/me/ai", tags=["ai settings"])


def _status(row) -> dict:
    """返回 AI 配置状态（绝不包含 api_key 本身）。"""
    return {
        "has_own_key": bool(row["ai_api_key"]),
        "own_base_url": row["ai_base_url"],
        "own_model": row["ai_model"],
        "free_used": row["ai_free_used"],
        "free_limit": AI_FREE_LIMIT,
        "shared_available": bool(AI_API_KEY),  # 服务器是否配置了共享 key
        "default_base_url": AI_BASE_URL,
        "default_model": AI_MODEL,
    }


@router.get("")
def get_ai_status(user=Depends(get_current_user), db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return _status(row)


@router.put("")
def update_ai(payload: AIUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data:
        db.execute("UPDATE users SET ai_api_key = ? WHERE id = ?", (data["api_key"] or None, user["id"]))
    if "base_url" in data:
        db.execute("UPDATE users SET ai_base_url = ? WHERE id = ?", (data["base_url"] or None, user["id"]))
    if "model" in data:
        db.execute("UPDATE users SET ai_model = ? WHERE id = ?", (data["model"] or None, user["id"]))
    row = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return _status(row)
