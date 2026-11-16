#!/bin/bash
# Deploy fleshed-out build to VPS. Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi
git -C src pull --ff-only
cp src/infra/vps-refresh.sh vps-refresh.sh
export COMPOSE_PROJECT_NAME=beosabasivps
docker compose -f vps/compose.yaml build api
bash vps-refresh.sh
