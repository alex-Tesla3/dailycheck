import re
from datetime import date, datetime, time as dt_time
from typing import Optional

from pydantic import BaseModel, Field, field_validator

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------- 认证 ----------
class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    invite_code: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if any(ch.isspace() for ch in v):
            raise ValueError("用户名不能包含空格")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_disabled: bool

    model_config = {"from_attributes": True}


# ---------- 习惯 ----------
class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    value_label: Optional[str] = Field(default=None, max_length=32)
    reminder_time: Optional[str] = None
    reminder_enabled: bool = False
    color: str = "#4f8cff"
    sort_order: int = 0

    @field_validator("reminder_time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not TIME_RE.match(v):
            raise ValueError("提醒时间格式应为 HH:MM")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("颜色格式应为 #RRGGBB")
        return v.lower()


class HabitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    value_label: Optional[str] = Field(default=None, max_length=32)
    reminder_time: Optional[str] = None
    reminder_enabled: Optional[bool] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator("reminder_time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not TIME_RE.match(v):
            raise ValueError("提醒时间格式应为 HH:MM")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("颜色格式应为 #RRGGBB")
        return v.lower()


# ---------- 打卡 ----------
class CheckinUpsert(BaseModel):
    done: bool = True
    value: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)


# ---------- 血压 ----------
class BPCreate(BaseModel):
    date: str
    time: Optional[str] = None
    systolic: int = Field(ge=50, le=300)
    diastolic: int = Field(ge=30, le=200)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not DATE_RE.match(v):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not TIME_RE.match(v):
            raise ValueError("时间格式应为 HH:MM")
        return v


class BPUpdate(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    systolic: Optional[int] = Field(default=None, ge=50, le=300)
    diastolic: Optional[int] = Field(default=None, ge=30, le=200)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not DATE_RE.match(v):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not TIME_RE.match(v):
            raise ValueError("时间格式应为 HH:MM")
        return v


# ---------- 管理 ----------
class InviteCodeCreate(BaseModel):
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)


class MemberUpdate(BaseModel):
    is_disabled: Optional[bool] = None


# ---------- 推送 ----------
class PushSubscribe(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


# ---------- 指标（体重等） ----------
class MetricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    value: float = Field(ge=0, le=1000)
    unit: Optional[str] = Field(default=None, max_length=16)
    date: str
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not DATE_RE.match(v):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        return v


class MetricUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    value: Optional[float] = Field(default=None, ge=0, le=1000)
    unit: Optional[str] = Field(default=None, max_length=16)
    date: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not DATE_RE.match(v):
            raise ValueError("日期格式应为 YYYY-MM-DD")
        return v
