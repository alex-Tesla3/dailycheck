"""应用配置：从环境变量读取，支持 Docker 部署时通过环境注入。"""
import os
from pathlib import Path


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = _ensure_dir(Path(os.environ.get("DATA_DIR", "./data")).expanduser())
DB_PATH = DATA_DIR / "habits.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 天

VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")
VAPID_KEYS_PATH = DATA_DIR / "vapid.json"

TZ = os.environ.get("TZ", "Asia/Shanghai")

START_SCHEDULER = os.environ.get("START_SCHEDULER", "1") != "0"

# ---- AI 分析（OpenAI 兼容接口，可对接 OpenAI / DeepSeek / Moonshot / 智谱等）----
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
AI_MODEL = os.environ.get("AI_MODEL", "deepseek-chat")
AI_FREE_LIMIT = max(0, int(os.environ.get("AI_FREE_LIMIT", "5")))  # 共享 key 每用户免费次数
