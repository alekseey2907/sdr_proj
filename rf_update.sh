#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:-100.70.123.76}"
USER_NAME="${SSH_USER:-root}"
RF_ROOT="${RF_ROOT:-/opt/skyshield/sdr_proj}"
BRANCH="${BRANCH:-master}"

ssh "${USER_NAME}@${TARGET_HOST}" "bash -s" <<EOF
set -euo pipefail
cd '${RF_ROOT}'
if [ ! -d .git ]; then
  echo 'ERROR: no .git in ${RF_ROOT}'
  exit 2
fi
git fetch --all --prune
git checkout '${BRANCH}'
git pull --ff-only origin '${BRANCH}'
chmod +x scripts/orangepi_install.sh
./scripts/orangepi_install.sh
systemctl daemon-reload
systemctl restart skyshield-backend.service skyshield-sdr-worker.service
systemctl --no-pager --full status skyshield-backend.service skyshield-sdr-worker.service
EOF

echo
echo "RF update finished successfully on ${TARGET_HOST}."
