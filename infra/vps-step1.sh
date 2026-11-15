#!/bin/bash
# BeosaBasi VPS deploy step 1: secrets + garage config. Run as beosabasi.
set -euo pipefail
cd /opt/beosabasi

W=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
A=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
S=$(python3 -c "import secrets;print(secrets.token_hex(32))")
R=$(python3 -c "import secrets;print(secrets.token_hex(32))")
G=$(python3 -c "import secrets;print(secrets.token_hex(16))")
SALT=$(python3 -c "import secrets;print(secrets.token_hex(16))")

cat > .env <<EOF
BEOSABASI_WORKER_TOKEN=$W
BEOSABASI_ADMIN_TOKEN=$A
BEOSABASI_IP_HASH_SALT=$SALT
BEOSABASI_CORS_ORIGINS=https://boxed-dialog-punch-nelson.trycloudflare.com
S3_REGION=garage
S3_BUCKET=beosabasi
S3_KEY_ID=beosabasi01
S3_KEY_SECRET=$S
S3_FORCE_PATH_STYLE=1
GARAGE_RPC_SECRET=$R
GARAGE_ADMIN_TOKEN=${G}-admin
GARAGE_METRICS_TOKEN=${G}-metrics
EOF
chmod 600 .env
echo ENV-OK

sed -e "s/__RPC_SECRET__/$R/" \
    -e "s/__ADMIN_TOKEN__/${G}-admin/" \
    -e "s/__METRICS_TOKEN__/${G}-metrics/" \
    src/infra/garage.vps.toml > garage.toml
echo GARAGE-OK
