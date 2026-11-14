"""TK-040: `make dev-web` — Vite dev server against the mock API.

The mock itself runs via `npm run mock:api` (Prism on :4010, TK-001).
Vite reads apps/web/.env.development, which already points
VITE_API_BASE_URL at the mock, so plain `npm run dev` just works.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP = os.path.join(ROOT, "apps", "web")


def run(cmd):
    shell = os.name == "nt" and shutil.which(cmd[0]) is not None
    return subprocess.run(cmd, cwd=WEB_APP, shell=shell).returncode


def main():
    print("[dev-web] mock API : `npm run mock:api` di apps/web (Prism :4010).")
    print("[dev-web] Vite memakai .env.development -> VITE_API_BASE_URL=:4010.")
    if shutil.which("npm") is None:
        print("[dev-web] npm tidak ditemukan.")
        return 1
    return run(["npm", "run", "dev"])


if __name__ == "__main__":
    sys.exit(main())
