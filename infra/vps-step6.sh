#!/bin/bash
# BeosaBasi VPS deploy step 6: api tunnel, print URL.
# Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi

pkill -f 'cloudflared tunnel --url http://127.0.0.1:18082' 2>/dev/null || true
rm -f api-tunnel.log
nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:18082 \
  > api-tunnel.log 2>&1 &
URL=""
for i in $(seq 1 20); do
  sleep 3
  URL=$(grep -o 'https://[^ ]*trycloudflare.com' api-tunnel.log 2>/dev/null \
    | head -1 || true)
  if [ -n "$URL" ]; then break; fi
done
if [ -z "$URL" ]; then echo "API TUNNEL GAGAL"; tail -5 api-tunnel.log; exit 1; fi
echo "API_URL=$URL"
echo "$URL" > api-url.txt
curl -s -o /dev/null -w 'via-tunnel:%{http_code}\n' "$URL/healthz"
