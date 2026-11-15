"""ASGI entrypoint. `uvicorn api.main:app`.

Configuration is environment-only (see api.config.Settings). The in-memory
fake backend is still available with BEOSABASI_FAKE=1 for the TK-002 demo.
"""

from api.app import create_app

app = create_app()
