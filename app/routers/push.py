from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from ..auth import get_current_user
from ..db import get_db
from ..push_service import get_vapid_public_key
from ..schemas import PushSubscribe

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-public-key")
def vapid_public_key():
    return {"public_key": get_vapid_public_key()}


@router.post("/subscribe")
def subscribe(payload: PushSubscribe, user=Depends(get_current_user), db: Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id FROM push_subscriptions WHERE endpoint = ?", (payload.endpoint,)
    ).fetchone()
    if row:
        db.execute(
            "UPDATE push_subscriptions SET user_id = ?, p256dh = ?, auth = ? WHERE id = ?",
            (user["id"], payload.p256dh, payload.auth, row["id"]),
        )
    else:
        db.execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?, ?, ?, ?)",
            (user["id"], payload.endpoint, payload.p256dh, payload.auth),
        )
    return {"ok": True}


@router.delete("/subscribe")
def unsubscribe(endpoint: str = Query(...), user=Depends(get_current_user), db: Connection = Depends(get_db)):
    db.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    return {"ok": True}
