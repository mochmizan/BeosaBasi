#!/bin/bash
# BeosaBasi VPS refresh: (re)start tunnels, update S3_ENDPOINT, restart API.
# Run as beosabasi. Safe to run anytime; also runs at boot via cron @reboot.
# Prints the three public URLs at the end.
set -euo pipefail
cd /opt/beosabasi
LOG=refresh.log

start_tunnel() { # $1=name $2=local-port $3=logfile
  pkill -f "cloudflared tunnel --url http://127.0.0.1:$2" 2>/dev/null || true
  rm -f "$3"
  nohup /usr/local/bin/cloudflared tunnel --url "http://127.0.0.1:$2" \
    > "$3" 2>&1 &
  local url=""
  for _ in $(seq 1 20); do
    sleep 3
    url=$(grep -o 'https://[^ ]*trycloudflare.com' "$3" 2>/dev/null \
      | head -1 || true)
    if [ -n "$url" ]; then break; fi
  done
  if [ -z "$url" ]; then echo "$1 TUNNEL GAGAL"; tail -5 "$3"; exit 1; fi
  echo "$url"
}

S3_URL=$(start_tunnel s3 3900 s3-tunnel.log)
echo "S3_URL=$S3_URL" | tee -a "$LOG"

if grep -q '^S3_ENDPOINT=' .env; then
  sed -i "s|^S3_ENDPOINT=.*|S3_ENDPOINT=$S3_URL|" .env
else
  echo "S3_ENDPOINT=$S3_URL" >> .env
fi

# Containers survive reboot via restart:unless-stopped; just ensure they're up
# and recreate api so the new S3_ENDPOINT takes effect.
export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml up -d

for _ in $(seq 1 24); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18082/healthz \
    || true)
  if [ "$CODE" = 200 ]; then break; fi
  sleep 5
done
[ "$CODE" = 200 ] || { echo "API TIDAK SEHAT"; exit 1; }
echo API-HEALTHY

API_URL=$(start_tunnel api 18082 api-tunnel.log)
echo "$API_URL" > api-url.txt
echo "API_URL=$API_URL" | tee -a "$LOG"

WEB_URL=$(start_tunnel web 18081 web-tunnel.log)
echo "$WEB_URL" > web-url.txt
echo "WEB_URL=$WEB_URL" | tee -a "$LOG"
echo REFRESH-OK
