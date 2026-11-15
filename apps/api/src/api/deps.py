"""FastAPI dependencies: DB connection, identity, storage, worker auth."""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Request, Response

from api import dal
from api.config import Settings
from api.db import connect
from api.errors import ApiError
from api.identity import Identity, hash_token, resolve_identity
from api.storage import Storage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def db_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def identity(request: Request, response: Response,
             conn: sqlite3.Connection = Depends(db_conn)) -> Identity:
    ident = resolve_identity(request, response, conn, get_settings(request))
    request.state.user_id = ident.user_id
    request.state.ip_hash = ident.ip_hash
    return ident


def worker_identity(request: Request, conn: sqlite3.Connection = Depends(db_conn),
                    settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise ApiError(401, "INTERNAL", "Token pekerja diperlukan.")
    token = header[7:].strip()
    if not token:
        raise ApiError(401, "INTERNAL", "Token pekerja tidak valid.")

    worker: dict[str, Any] | None = None
    if settings.worker_token and secrets.compare_digest(token, settings.worker_token):
        worker_id = request.headers.get("x-worker-id", "worker-env").strip()
        worker = {"id": worker_id or "worker-env", "versi": "",
                  "token_hash": hash_token(f"{token}:{worker_id or 'worker-env'}"),
                  "raw_token": token}
    else:
        worker = dal.worker_by_token_hash(conn, hash_token(token))
    if worker is None:
        raise ApiError(401, "INTERNAL", "Token pekerja tidak valid.")
    request.state.worker_id = worker["id"]
    return worker
