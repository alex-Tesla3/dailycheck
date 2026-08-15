from fastapi import APIRouter, Depends, HTTPException, Query

from ..analysis import _serialize, generate_analysis
from ..auth import get_current_user
from ..db import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("")
def create_analysis(days: int = Query(30, ge=7, le=90),
                    user=Depends(get_current_user), db=Depends(get_db)):
    """基于近 N 天数据调用 AI 生成个性化分析，并保存记录。"""
    return generate_analysis(db, user["id"], days)


@router.get("")
def list_analyses(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM analyses WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user["id"],)
    ).fetchall()
    return [_serialize(r) for r in rows]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.execute(
        "SELECT * FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, user["id"])
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return _serialize(row)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    db.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, user["id"]))
