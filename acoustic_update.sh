#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:-100.70.123.76}"
USER_NAME="${SSH_USER:-root}"
ACOUSTIC_ROOT="${ACOUSTIC_ROOT:-/opt/skyshield-acoustic}"
BRANCH="${BRANCH:-master}"

ssh "${USER_NAME}@${TARGET_HOST}" "bash -s" <<EOF
set -euo pipefail
cd '${ACOUSTIC_ROOT}'
if [ ! -d .git ]; then
  echo 'ERROR: no .git in ${ACOUSTIC_ROOT}'
  exit 2
fi
git fetch --all --prune
git checkout '${BRANCH}'
git pull --ff-only origin '${BRANCH}'
if [ -x scripts/orangepi_install.sh ]; then
  ./scripts/orangepi_install.sh
fi
systemctl daemon-reload
systemctl restart skyshield-acoustic-backend.service skyshield-acoustic-worker.service
systemctl --no-pager --full status skyshield-acoustic-backend.service skyshield-acoustic-worker.service
EOF

echo
echo "Acoustic update finished successfully on ${TARGET_HOST}."
