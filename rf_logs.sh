#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:-100.70.123.76}"
USER_NAME="${SSH_USER:-root}"

ssh "${USER_NAME}@${TARGET_HOST}" "journalctl --no-pager -f --since '15 minutes ago' -u skyshield-backend.service -u skyshield-sdr-worker.service"
