"""后台定时提醒：独立线程每分钟检查“到点且当天未完成”的习惯并推送。"""
import logging
import threading
from datetime import datetime

import pytz

from .config import TZ
from .db import Database
from .push_service import SubscriptionGone, send_push

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread = None


def run_reminders_once() -> None:
    now = datetime.now(pytz.timezone(TZ))
    today = now.strftime("%Y-%m-%d")
    hm = now.strftime("%H:%M")

    db = Database()
    try:
        habits = db.execute(
            """SELECT * FROM habits
               WHERE reminder_enabled = 1 AND reminder_time = ?
                 AND (last_reminder_date IS NULL OR last_reminder_date != ?)""",
            (hm, today),
        ).fetchall()
        for habit in habits:
            already_done = db.execute(
                "SELECT 1 FROM checkins WHERE habit_id = ? AND date = ? AND done = 1",
                (habit["id"], today),
            ).fetchone()
            if already_done:
                db.execute("UPDATE habits SET last_reminder_date = ? WHERE id = ?", (today, habit["id"]))
                continue

            subs = db.execute(
                "SELECT * FROM push_subscriptions WHERE user_id = ?", (habit["user_id"],)
            ).fetchall()
            for sub in subs:
                try:
                    send_push(sub["endpoint"], sub["p256dh"], sub["auth"],
                              "打卡提醒", f"{habit['name']} 今天还没打卡，记得完成哦")
                except SubscriptionGone:
                    db.execute("DELETE FROM push_subscriptions WHERE id = ?", (sub["id"],))
                except Exception:
                    logger.exception("推送失败 habit_id=%s", habit["id"])
            db.execute("UPDATE habits SET last_reminder_date = ? WHERE id = ?", (today, habit["id"]))
        db.commit()
    finally:
        db.close()


def _loop() -> None:
    while not _stop.is_set():
        try:
            run_reminders_once()
        except Exception:
            logger.exception("提醒任务执行失败")
        _stop.wait(30)


def start_scheduler() -> threading.Thread:
    global _thread
    if _thread is not None and _thread.is_alive():
        return _thread
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="reminder-scheduler", daemon=True)
    _thread.start()
    return _thread
