#!/usr/bin/env bash
# Сбор инвентаря парка SkyShield (macOS/Linux).
# Использование:
#   ./scripts/collect_inventory.sh fleet_hosts.txt [out.csv]
# Файл fleet_hosts.txt: по одному хосту (Tailscale IP или имя) на строку.
set -euo pipefail

HOSTS_FILE="${1:-}"
OUT_FILE="${2:-fleet_inventory.csv}"
SSH_USER="${SSH_USER:-root}"

if [ -z "$HOSTS_FILE" ] || [ ! -f "$HOSTS_FILE" ]; then
  echo "Usage: $0 <hosts_file> [out_csv]" >&2
  exit 1
fi

REMOTE_CMD="cat /etc/skyshield/device.json 2>/dev/null; echo '---'; cat /opt/skyshield/sdr_proj/VERSION 2>/dev/null"

echo "host,device_id,version,checked_at" > "$OUT_FILE"

while IFS= read -r host; do
  host="$(printf '%s' "$host" | tr -d '[:space:]')"
  [ -z "$host" ] && continue
  case "$host" in \#*) continue ;; esac

  echo "Collecting from $host ..."
  device_id="unreachable"
  version="unknown"

  if output="$(ssh -o ConnectTimeout=8 "${SSH_USER}@${host}" "$REMOTE_CMD" 2>/dev/null)"; then
    json_part="${output%%---*}"
    version_part="${output##*---}"
    device_id="$(printf '%s' "$json_part" | sed -n 's/.*"device_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
    [ -z "$device_id" ] && device_id="unknown"
    version="$(printf '%s' "$version_part" | tr -d '[:space:]')"
    [ -z "$version" ] && version="unknown"
  fi

  printf '%s,%s,%s,%s\n' "$host" "$device_id" "$version" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT_FILE"
done < "$HOSTS_FILE"

echo
echo "Inventory written to $OUT_FILE"
cat "$OUT_FILE"
