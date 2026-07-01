#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:-100.70.123.76}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/rf_update.sh" "${TARGET_HOST}"
"${SCRIPT_DIR}/acoustic_update.sh" "${TARGET_HOST}"

echo
echo "RF + Acoustic update finished successfully on ${TARGET_HOST}."
