"""
Сбор обучающих данных ELRS 868 МГц с RTL-SDR.
Использование:
    python scripts/collect_elrs_samples.py --label elrs_active --duration 30
    python scripts/collect_elrs_samples.py --label noise_baseline --duration 30

Метки для сбора датасета:
    noise_baseline  — пульт выключен, только фоновый шум
    elrs_idle       — пульт включён, стики не трогаешь
    elrs_active     — активно двигаешь все стики
    elrs_arming     — arm/disarm (угловой правый стик вниз-вправо)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# ─── Параметры захвата ────────────────────────────────────────────────────────
CENTER_FREQ_HZ = 868_000_000.0   # ELRS EU 868 МГц
SAMPLE_RATE_HZ = 2_400_000.0     # 2.4 МГц — накрывает диапазон 863–870 МГц целиком
GAIN_DB        = 35.0            # Фиксированное усиление (совпадает с NARROWBAND_GAIN в sdr_worker.py)
CHUNK_SAMPLES  = 65_536          # Размер одного чанка (совпадает с NARROWBAND_CAPTURE_SIZE)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "elrs_raw"
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Сбор IQ-данных ELRS 868 МГц")
    p.add_argument("--label", required=True,
                   choices=["noise_baseline", "elrs_idle", "elrs_active", "elrs_arming"],
                   help="Метка сценария")
    p.add_argument("--duration", type=float, default=30.0,
                   help="Длительность записи в секундах (по умолчанию 30)")
    p.add_argument("--device-index", type=int, default=0,
                   help="Индекс RTL-SDR устройства (по умолчанию 0)")
    p.add_argument("--rtl-tcp", type=str, default=None,
                   metavar="HOST:PORT",
                   help="Подключиться через rtl_tcp вместо USB, например 127.0.0.1:1234")
    return p.parse_args()


def open_sdr(args: argparse.Namespace):
    try:
        from rtlsdr import RtlSdr
    except ImportError:
        print("[ERROR] pyrtlsdr не найден. Установи: pip install pyrtlsdr")
        sys.exit(1)

    if args.rtl_tcp:
        host, port = args.rtl_tcp.split(":")
        sdr = RtlSdr(device_index=f"rtl_tcp://{host}:{port}")
    else:
        sdr = RtlSdr(device_index=args.device_index)

    sdr.sample_rate = SAMPLE_RATE_HZ
    sdr.center_freq = CENTER_FREQ_HZ
    sdr.gain        = GAIN_DB
    print(f"[SDR] F={sdr.center_freq/1e6:.3f} МГц  SR={sdr.sample_rate/1e6:.2f} МГц  Gain={sdr.gain} дБ")
    return sdr


def collect(sdr, duration_sec: float, label: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_samples = int(SAMPLE_RATE_HZ * duration_sec)
    chunks_needed = max(1, total_samples // CHUNK_SAMPLES)
    all_chunks: list[np.ndarray] = []

    print(f"[REC] Метка: {label}  |  {duration_sec:.0f} сек  |  {chunks_needed} чанков")
    print("      Нажми Ctrl+C для досрочного завершения\n")

    start = time.time()
    for i in range(chunks_needed):
        elapsed = time.time() - start
        remaining = duration_sec - elapsed
        bar_len = 30
        filled = int(bar_len * i / chunks_needed)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {elapsed:.1f}/{duration_sec:.0f}с  осталось {remaining:.1f}с  ", end="", flush=True)

        chunk = sdr.read_samples(CHUNK_SAMPLES)
        all_chunks.append(chunk.astype(np.complex64))

    print(f"\r  [{'█'*bar_len}] {duration_sec:.0f}/{duration_sec:.0f}с  готово!       ")

    raw = np.concatenate(all_chunks)
    ts  = int(time.time())
    npy_path = OUTPUT_DIR / f"{label}_{ts}.npy"
    meta_path = OUTPUT_DIR / f"{label}_{ts}.json"

    np.save(npy_path, raw)

    meta = {
        "label":       label,
        "timestamp":   ts,
        "center_freq_hz": CENTER_FREQ_HZ,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "gain_db":     GAIN_DB,
        "duration_sec": duration_sec,
        "num_samples": len(raw),
        "file":        npy_path.name,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[SAVE] {npy_path}")
    print(f"[META] {meta_path}")
    return npy_path


def show_spectrum_preview(npy_path: Path) -> None:
    """Быстрый текстовый превью спектра без matplotlib"""
    data = np.load(npy_path)
    chunk = data[:8192]
    window = np.hanning(len(chunk))
    fft_mag = np.abs(np.fft.fftshift(np.fft.fft(chunk * window)))
    psd_db  = 20 * np.log10(fft_mag + 1e-12)

    freqs_mhz = (np.fft.fftshift(np.fft.fftfreq(len(chunk), d=1/SAMPLE_RATE_HZ)) + CENTER_FREQ_HZ) / 1e6

    peak_idx = int(np.argmax(psd_db))
    print(f"\n[PREVIEW] Пик: {freqs_mhz[peak_idx]:.3f} МГц  |  {psd_db[peak_idx]:.1f} дБ")
    print(f"          Мин: {psd_db.min():.1f} дБ  |  Макс: {psd_db.max():.1f} дБ  |  Медиана: {np.median(psd_db):.1f} дБ")
    print(f"          Примерный порог для config_drone_defense.yaml: threshold_db: {np.median(psd_db) + 10:.0f}")


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("  ELRS 868 МГц — Сборщик обучающих данных")
    print("=" * 60)

    label_hints = {
        "noise_baseline": "Убедись что пульт ВЫКЛЮЧЕН",
        "elrs_idle":      "Включи пульт. Стики НЕ трогай",
        "elrs_active":    "Включи пульт. Активно двигай ВСЕ стики",
        "elrs_arming":    "Включи пульт. Выполни arm → disarm несколько раз",
    }
    print(f"\n[HINT] {label_hints[args.label]}")
    input("  Нажми Enter когда будешь готов...\n")

    sdr = open_sdr(args)
    try:
        npy_path = collect(sdr, args.duration, args.label)
    except KeyboardInterrupt:
        print("\n[!] Прервано пользователем")
        sdr.close()
        sys.exit(0)
    finally:
        sdr.close()

    show_spectrum_preview(npy_path)
    print("\n[OK] Готово. Следующий шаг:")
    print(f"     python scripts/collect_elrs_samples.py --label <следующая_метка> --duration {args.duration:.0f}")


if __name__ == "__main__":
    main()
