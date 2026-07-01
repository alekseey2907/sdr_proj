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

chmod +x "$ROOT_DIR/scripts/run_backend.sh"
chmod +x "$ROOT_DIR/scripts/run_sdr_worker.sh"

echo "Установка завершена. Проверь файл deploy/orangepi/skyshield.env и затем запускай scripts/run_backend.sh и scripts/run_sdr_worker.sh"