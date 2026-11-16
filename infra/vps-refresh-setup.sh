#!/bin/bash
# Install refresh: restart policy + @reboot cron. Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi
which cron crontab cloudflared 2>&1 || true
# Apply restart:unless-stopped from repo compose (already synced to vps/).
sed -i '/^    restart: unless-stopped$/d' vps/compose.yaml
python3 - <<'EOF'
import re
p = "vps/compose.yaml"
s = open(p).read()
s = s.replace("""  api:
    build:""", """  api:
    restart: unless-stopped
    build:""")
s = s.replace("""  s3:
    image:""", """  s3:
    restart: unless-stopped
    image:""")
open(p, "w").write(s)
EOF
grep -n "restart:" vps/compose.yaml
export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml up -d
# @reboot: refresh tunnels + ensure stack, log to refresh-boot.log
( crontab -l 2>/dev/null | grep -v "vps-refresh.sh" ; \
  echo "@reboot sleep 30 && /opt/beosabasi/vps-refresh.sh >> /opt/beosabasi/refresh-boot.log 2>&1" ) \
  | crontab -
crontab -l | grep vps-refresh
echo SETUP-OK
