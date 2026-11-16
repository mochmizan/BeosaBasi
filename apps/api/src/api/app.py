"""Application factory: routers, CORS, error envelope, retention sweeper."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import schemas
from api.config import Settings
from api.db import connect, migrate
from api.errors import register_error_handlers
from api.health import health_status
from api.observability import install_middleware, setup_logging
from api.retention import audit_k4, sweep
from api.storage import Storage, build_storage
from api.timeutil import utcnow

log = logging.getLogger("beosabasi.app")


async def _sweep_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    last_audit: str | None = None
    while True:
        await asyncio.sleep(settings.sweeper_interval_seconds)
        try:
            await asyncio.to_thread(_sweep_once, app)
            today = utcnow().date().isoformat()
            if today != last_audit:
                last_audit = today
                await asyncio.to_thread(_audit_once, app)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive background loop
            log.exception("penyapu_gagal")


def _sweep_once(app: FastAPI) -> dict[str, int]:
    settings: Settings = app.state.settings
    conn = connect(settings.db_path)
    try:
        return sweep(conn, app.state.storage, settings)
    finally:
        conn.close()


def _audit_once(app: FastAPI) -> dict[str, int]:
    """Daily K4 audit: orphan objects and audio past its 24 h retention."""
    settings: Settings = app.state.settings
    conn = connect(settings.db_path)
    try:
        report = audit_k4(conn, app.state.storage, settings)
    finally:
        conn.close()
    if report["objek_yatim"] or report["audio_terlambat_hapus"]:
        log.warning("audit_k4_anomali %s", report)
    else:
        log.info("audit_k4_bersih %s", report)
    return report


def create_app(settings: Settings | None = None,
               storage: Storage | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    setup_logging()
    migrate(settings.db_path)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if settings.sweeper_enabled:
            task = asyncio.create_task(_sweep_loop(app))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="BeosaBasi API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = storage or build_storage(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Session-Token"],
    )
    install_middleware(app)
    register_error_handlers(app)

    from api import exports, jobs, transcripts, uploads, worker_api

    app.include_router(uploads.router)
    app.include_router(jobs.router)
    app.include_router(worker_api.router)
    app.include_router(transcripts.router)
    app.include_router(exports.router)
    from api.observability import router as admin_router

    app.include_router(admin_router)

    if os.getenv("BEOSABASI_FAKE") == "1":
        # DEV ONLY (TK-002): seed a real queued job + silent WAV so
        # `worker demo` exercises the real worker routers. Never in production.
        from api.dev import router as dev_router

        app.include_router(dev_router)

    @app.get("/healthz", response_model=schemas.Health)
    def healthz() -> schemas.Health:
        conn = connect(settings.db_path)
        try:
            active = jobs._worker_active(conn, settings)
        except sqlite3.Error:
            active = False
        finally:
            conn.close()
        return schemas.Health(
            status=health_status()["status"],
            worker_active=active,
        )

    return app
