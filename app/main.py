from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SESSION_MAX_AGE, SESSION_SECRET, START_SCHEDULER
from .db import init_db
from .routers import admin, auth, bp, checkins, habits, push, stats

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
SW_FILE = STATIC_DIR / "sw.js"
MANIFEST_FILE = STATIC_DIR / "manifest.webmanifest"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if START_SCHEDULER:
        from .scheduler import start_scheduler

        app.state.scheduler = start_scheduler()
    yield


app = FastAPI(title="每日打卡", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
)

for router in (auth.router, habits.router, checkins.router, stats.router,
               bp.router, push.router, admin.router):
    app.include_router(router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(INDEX_FILE)


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(SW_FILE, media_type="text/javascript")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(MANIFEST_FILE, media_type="application/manifest+json")
