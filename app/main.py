from contextlib import asynccontextmanager
import base64
import secrets

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pathlib import Path
from app.api.routes import router as api_router
from app.core.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler(scheduler_task)


app = FastAPI(title="TR → Actual Sync (backend)", lifespan=lifespan)


@app.middleware("http")
async def optional_basic_auth(request: Request, call_next):
    username = settings.basic_auth_username
    password = settings.basic_auth_password
    if not username and not password:
        return await call_next(request)
    if request.url.path == "/health":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    scheme, _, credentials = auth.partition(" ")
    valid = False
    if scheme.lower() == "basic" and credentials:
        try:
            decoded = base64.b64decode(credentials).decode("utf-8")
            provided_user, _, provided_password = decoded.partition(":")
            valid = (
                secrets.compare_digest(provided_user, username)
                and secrets.compare_digest(provided_password, password)
            )
        except Exception:
            valid = False

    if not valid:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="TR Actual Sync"'},
        )
    return await call_next(request)

app.include_router(api_router, prefix="", tags=["tr-sync"])

# Mount static files for a minimal UI
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
