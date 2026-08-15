"""时区相关的日期工具：所有“今天”逻辑按 Asia/Shanghai 计算。"""
from datetime import date, datetime

import pytz

from .config import TZ

_tz = pytz.timezone(TZ)


def now_local() -> datetime:
    return datetime.now(_tz)


def today_date() -> date:
    return now_local().date()


def today_str() -> str:
    return today_date().strftime("%Y-%m-%d")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def combine_local(date_str: str, time_str: str) -> datetime:
    """把 YYYY-MM-DD 与 HH:MM 组合成本地时间（naive，语义为 Asia/Shanghai）。"""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def utc_now_str() -> str:
    """UTC 时间字符串（YYYY-MM-DD HH:MM:SS），跨 SQLite/Postgres 统一存储。"""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
