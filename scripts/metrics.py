"""TK-029 admin metrics script (stdlib only).

Usage:
  set BEOSABASI_API_URL=https://api.example.id
  set BEOSABASI_ADMIN_TOKEN=...
  python scripts/metrics.py
"""

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.getenv("BEOSABASI_API_URL", "http://localhost:8000").rstrip("/")
    token = os.getenv("BEOSABASI_ADMIN_TOKEN", "")
    if not token:
        print("BEOSABASI_ADMIN_TOKEN belum diisi.", file=sys.stderr)
        return 2
    req = urllib.request.Request(f"{base}/api/admin/metrics",
                                 headers={"X-Admin-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode(errors='replace')}",
              file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"tidak bisa menghubungi {base}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
