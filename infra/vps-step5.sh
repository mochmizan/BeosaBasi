#!/bin/bash
# BeosaBasi VPS deploy step 5: s3 tunnel -> S3_ENDPOINT -> api up + health.
# Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi

pkill -f 'cloudflared tunnel --url http://127.0.0.1:3900' 2>/dev/null || true
rm -f s3-tunnel.log
nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:3900 \
  > s3-tunnel.log 2>&1 &
URL=""
for i in $(seq 1 20); do
  sleep 3
  URL=$(grep -o 'https://[^ ]*trycloudflare.com' s3-tunnel.log 2>/dev/null \
    | head -1 || true)
  if [ -n "$URL" ]; then break; fi
done
if [ -z "$URL" ]; then echo "S3 TUNNEL GAGAL"; tail -5 s3-tunnel.log; exit 1; fi
echo "S3_URL=$URL"

if grep -q '^S3_ENDPOINT=' .env; then
  sed -i "s|^S3_ENDPOINT=.*|S3_ENDPOINT=$URL|" .env
else
  echo "S3_ENDPOINT=$URL" >> .env
fi

export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml up -d --build api
for i in $(seq 1 40); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18082/healthz \
    || true)
  if [ "$CODE" = 200 ]; then break; fi
  sleep 5
  if [ "$i" = 40 ]; then echo "API TIDAK SEHAT"; exit 1; fi
done
echo API-HEALTHY
curl -s http://127.0.0.1:18082/healthz | head -c 200; echo
