#!/bin/bash
# BeosaBasi VPS deploy step 3: isolated vps project + garage bootstrap.
# Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi

# Remove the colliding first attempt (wrong mount + shared network).
docker compose -f src/infra/compose.vps.yaml down 2>/dev/null || true
docker volume rm -f beosabasi_s3-data beosabasi_api-data 2>/dev/null || true

mkdir -p vps
cp src/infra/compose.vps.yaml vps/compose.yaml
cp garage.toml vps/garage.toml
chmod 600 vps/garage.toml
# Build context is relative to the compose file: vps/ -> ../src/apps/api
sed -i 's|context: ./src/apps/api|context: ../src/apps/api|' vps/compose.yaml
sed -i 's|./garage.vps.toml|./garage.toml|' vps/compose.yaml
# Isolate: own project name + own network (never touch beosabasi_beosabasi-net).
sed -i 's|^name: beosabasi$|name: beosabasivps|' vps/compose.yaml
sed -i 's|beosabasi-net:|beosabasivps-net:|' vps/compose.yaml
sed -i 's|- beosabasi-net|- beosabasivps-net|' vps/compose.yaml
grep -E '^name:|context:|garage.toml|net:' vps/compose.yaml

export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml up -d s3

set -a; source .env; set +a
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
