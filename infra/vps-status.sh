#!/bin/bash
cat /opt/beosabasi/api-url.txt; echo
grep -E '^S3_ENDPOINT=|^S3_BUCKET=' /opt/beosabasi/.env
cd /opt/beosabasi && export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml ps
echo '--- s3 tunnel ---'
grep -o 'https://[^ ]*trycloudflare.com' /opt/beosabasi/s3-tunnel.log | sort -u
