"""HTTP entry. Migrations finish before the process accepts traffic."""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from investigator_shared.secrets import install_redacting_logs

from api_app import cache, db, jobs, migrate
from api_app.auth import AuthGate
from api_app.auth import router as identity
from api_app.body_limit import BodyLimit
from api_app.config import get_settings
from api_app.routes.investigations import router as investigations
from api_app.routes.prompts import router as prompts
from api_app.routes.repositories import router as repositories

logging.basicConfig(level=logging.INFO, format="%(message)s")
install_redacting_logs()


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate.apply()
    stop = asyncio.Event()
    worker = asyncio.create_task(jobs.run_loop(stop))
    yield
    stop.set()
    await worker


app = FastAPI(lifespan=lifespan)
app.add_middleware(AuthGate)
app.add_middleware(BodyLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(identity)
app.include_router(repositories)
app.include_router(investigations)
app.include_router(prompts)


@app.get("/health")
async def health():
    """Process health. This does not check Postgres or Redis."""
    return {"status": "ok", "service": "api"}


@app.get("/ready")
async def ready():
    """Postgres and Redis are reachable."""
    try:
        db.ping()
        cache.ping()
    except Exception:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    return {"status": "ok", "service": "api"}


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
