#!/bin/bash
# BeosaBasi VPS deploy step 4: garage bootstrap only (idempotent).
# Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi
set -a; source .env; set +a
export COMPOSE_PROJECT_NAME=beosabasivps
g() { docker compose -f vps/compose.yaml exec -T s3 \
  /garage -c /etc/garage.toml "$@"; }

for i in $(seq 1 30); do
  OUT=$(g status 2>&1 || true)
  if echo "$OUT" | grep -q HEALTHY; then break; fi
  sleep 2
  if [ "$i" = 30 ]; then echo "GARAGE TIDAK SEHAT"; echo "$OUT"; exit 1; fi
done
echo GARAGE-HEALTHY

NODE=$(g status | grep -oE '\b[0-9a-f]{16}\b' | head -1)
echo "NODE=$NODE"
if g layout show 2>&1 | grep -q "No nodes currently have a role"; then
  g layout assign -z dc1 -c 5G "$NODE"
  g layout apply --version 1 || true
fi
g bucket create "$S3_BUCKET" 2>&1 || true
if ! g key list 2>/dev/null | grep -q "$S3_KEY_ID"; then
  g key import --yes -n beosabasi-vps "$S3_KEY_ID" "$S3_KEY_SECRET"
fi
g bucket allow --read --write --owner "$S3_BUCKET" --key "$S3_KEY_ID"
echo S3-READY
