#!/bin/bash
cd /opt/beosabasi && export COMPOSE_PROJECT_NAME=beosabasivps
echo '--- containers ---'
docker compose -f vps/compose.yaml ps
echo '--- health ---'
curl -s -o /dev/null -w 'api-local:%{http_code}\n' http://127.0.0.1:18082/healthz
echo '--- disk ---'
df -h / /opt | tail -2
echo '--- urls ---'
cat api-url.txt web-url.txt 2>/dev/null
grep -o 'https://[^ ]*trycloudflare.com' s3-tunnel.log 2>/dev/null | sort -u
echo '--- src ---'
git -C src log --oneline -1; git -C src status --short | head -3
