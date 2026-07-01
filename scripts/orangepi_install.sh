#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  librtlsdr-dev \
  rtl-sdr \
  libusb-1.0-0-dev \
  libopenblas-dev \
  pkg-config \
  fonts-dejavu-core

if [ ! -d "$ROOT_DIR/.venv" ]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi

. "$ROOT_DIR/.venv/bin/activate"
python -m pip install --upgrade pip wheel "setuptools<81"
python -m pip install -r "$ROOT_DIR/backend/requirements.txt"
python -m pip install requests numpy "setuptools<81" "pyrtlsdr>=0.3.0,<0.4"

mkdir -p "$ROOT_DIR/backend/data"

if [ ! -f "$ROOT_DIR/deploy/orangepi/skyshield.env" ]; then
  cp "$ROOT_DIR/deploy/orangepi/skyshield.env.example" "$ROOT_DIR/deploy/orangepi/skyshield.env"
fi

# Генерация уникальной идентичности устройства при первом запуске.
ENV_FILE="$ROOT_DIR/deploy/orangepi/skyshield.env"

_get_env_value() {
  # $1 = ключ; печатает значение (без ключа) или пусто
  sed -n "s/^$1=//p" "$ENV_FILE" | head -n1
}

_set_env_value() {
  # $1 = ключ, $2 = значение
  if grep -q "^$1=" "$ENV_FILE"; then
    tmp="$(mktemp)"
    grep -v "^$1=" "$ENV_FILE" > "$tmp"
    printf '%s=%s\n' "$1" "$2" >> "$tmp"
    install -m 600 "$tmp" "$ENV_FILE"
    rm -f "$tmp"
  else
    printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
  fi
}

CURRENT_DEVICE_ID="$(_get_env_value DEVICE_ID)"
if [ -z "$CURRENT_DEVICE_ID" ]; then
  if [ -r /etc/machine-id ]; then
    MID="$(cat /etc/machine-id)"
  else
    MID="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  SUFFIX="$(printf '%s' "$MID" | tail -c 8 | tr 'a-f' 'A-F')"
  _set_env_value DEVICE_ID "SKY-$SUFFIX"
  echo "Сгенерирован DEVICE_ID=SKY-$SUFFIX"
fi

CURRENT_DEVICE_TOKEN="$(_get_env_value DEVICE_TOKEN)"
if [ -z "$CURRENT_DEVICE_TOKEN" ]; then
  if command -v openssl >/dev/null 2>&1; then
    NEW_TOKEN="$(openssl rand -hex 24)"
  else
    NEW_TOKEN="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  _set_env_value DEVICE_TOKEN "$NEW_TOKEN"
  echo "Сгенерирован DEVICE_TOKEN (скрыт)"
fi

# Зеркалируем идентичность в /etc/skyshield/device.json для backend.
DEVICE_ID_VAL="$(_get_env_value DEVICE_ID)"
DEVICE_TOKEN_VAL="$(_get_env_value DEVICE_TOKEN)"
if [ -n "$DEVICE_ID_VAL" ] && [ -n "$DEVICE_TOKEN_VAL" ]; then
  sudo mkdir -p /etc/skyshield
  printf '{\n  "device_id": "%s",\n  "device_token": "%s"\n}\n' "$DEVICE_ID_VAL" "$DEVICE_TOKEN_VAL" | sudo tee /etc/skyshield/device.json >/dev/null
  sudo chmod 600 /etc/skyshield/device.json
fi

chmod 600 "$ENV_FILE" || true


chmod +x "$ROOT_DIR/scripts/run_backend.sh"
chmod +x "$ROOT_DIR/scripts/run_sdr_worker.sh"

echo "Установка завершена. Проверь файл deploy/orangepi/skyshield.env и затем запускай scripts/run_backend.sh и scripts/run_sdr_worker.sh"