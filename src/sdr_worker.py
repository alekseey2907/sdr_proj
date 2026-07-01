import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import requests


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LIBS_DIR = os.path.join(PROJECT_DIR, "libs")

if os.name == "nt" and os.path.exists(LIBS_DIR):
    os.environ["PATH"] = LIBS_DIR + os.pathsep + os.environ.get("PATH", "")
    print(f"[init] Добавлен путь к DLL: {LIBS_DIR}")


def _env_float(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return float(value)


def _env_int(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _default_scan_channels():
    return [
        {"freq": 869.0e6, "name": "868-870 MHz (Drone)"},
        {"freq": 1280.0e6, "name": "1279-1281 MHz (Drone)"},
    ]


def _load_scan_channels():
    raw = os.getenv("SCAN_CHANNELS_JSON")
    if not raw:
        return _default_scan_channels()

    try:
        channels = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный SCAN_CHANNELS_JSON: {exc}") from exc

    if not isinstance(channels, list) or not channels:
        raise RuntimeError("SCAN_CHANNELS_JSON должен быть непустым JSON-массивом")

    normalized = []
    for item in channels:
        if not isinstance(item, dict) or "freq" not in item:
            raise RuntimeError("Каждый канал должен содержать поле 'freq'")
        normalized.append(
            {
                "freq": float(item["freq"]),
                "name": str(item.get("name") or f"{float(item['freq']) / 1e6:.3f} MHz"),
            }
        )
    return normalized


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1/telemetry/")
DEVICE_ID = os.getenv("DEVICE_ID", "DRONE-HUNTER-01")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
NOTIFICATION_API_URL = os.getenv("NOTIFICATION_API_URL", "http://127.0.0.1:8000/api/v1/notifications/alert")
NOTIFICATION_GATEWAY_RETRY_SECONDS = _env_float("NOTIFICATION_GATEWAY_RETRY_SECONDS", 5.0)
TELEMETRY_POST_INTERVAL_SECONDS = _env_float("TELEMETRY_POST_INTERVAL_SECONDS", 1.0)
SDR_MODE = os.getenv("SDR_MODE", "usb").strip().lower()
RTL_TCP_HOST = os.getenv("RTL_TCP_HOST", "127.0.0.1")
RTL_TCP_PORT = _env_int("RTL_TCP_PORT", 1234)
RTLSDR_DEVICE_INDEX = os.getenv("RTLSDR_DEVICE_INDEX", "0")
SAMPLE_RATE = _env_float("SAMPLE_RATE", 2.4e6)
GAIN = os.getenv("GAIN", "auto")
READ_SIZE = _env_int("READ_SIZE", 4096)
SCAN_CHANNELS = _load_scan_channels()
CENTER_FREQ = SCAN_CHANNELS[0]["freq"]
NARROWBAND_868_870_START_HZ = 868e6
NARROWBAND_868_870_STOP_HZ = 870e6
NARROWBAND_868_870_CENTER_HZ = 869e6
NARROWBAND_1279_1281_START_HZ = 1279e6
NARROWBAND_1279_1281_STOP_HZ = 1281e6
NARROWBAND_1279_1281_CENTER_HZ = 1280e6
NARROWBAND_POINTS = _env_int("NARROWBAND_POINTS", 128)
NARROWBAND_CAPTURE_SIZE = _env_int("NARROWBAND_CAPTURE_SIZE", 8192)
NARROWBAND_FFT_SIZE = _env_int("NARROWBAND_FFT_SIZE", 2048)
NARROWBAND_SMOOTHING_ALPHA = _env_float("NARROWBAND_SMOOTHING_ALPHA", 0.28)
NARROWBAND_DBM_OFFSET = _env_float("NARROWBAND_DBM_OFFSET", -56.0)
NARROWBAND_USE_FIXED_GAIN = _env_bool("NARROWBAND_USE_FIXED_GAIN", True)
NARROWBAND_GAIN = _env_float("NARROWBAND_GAIN", 35.0)
NARROWBAND_PEAK_DELTA_DB = _env_float("NARROWBAND_PEAK_DELTA_DB", 6.0)
NARROWBAND_PEAK_THREAT_LEVEL = _env_float("NARROWBAND_PEAK_THREAT_LEVEL", 100.0)
NARROWBAND_EXTRA_REFRESH = _env_bool("NARROWBAND_EXTRA_REFRESH", False)
ELRS_NORMAL_PEAK_DELTA_DB = _env_float("ELRS_NORMAL_PEAK_DELTA_DB", 6.0)
ELRS_STRONG_PEAK_DELTA_DB = _env_float("ELRS_STRONG_PEAK_DELTA_DB", 10.0)
ELRS_STRONG_PEAK_IMMEDIATE = _env_bool("ELRS_STRONG_PEAK_IMMEDIATE", False)
ELRS_MIN_PEAK_POWER_DBM = _env_float("ELRS_MIN_PEAK_POWER_DBM", -92.0)
ELRS_ACTIVE_BIN_DELTA_DB = _env_float("ELRS_ACTIVE_BIN_DELTA_DB", 4.0)
ELRS_MIN_OCCUPIED_BW_MHZ = _env_float("ELRS_MIN_OCCUPIED_BW_MHZ", 0.20)
ELRS_MIN_ACTIVE_BINS = _env_int("ELRS_MIN_ACTIVE_BINS", 8)
ELRS_EVENT_WINDOW_SECONDS = _env_float("ELRS_EVENT_WINDOW_SECONDS", 30.0)
ELRS_WARNING_EVENTS = _env_int("ELRS_WARNING_EVENTS", 1)
ELRS_CRITICAL_EVENTS = _env_int("ELRS_CRITICAL_EVENTS", 2)
VIDEO_ACTIVE_BIN_DELTA_DB = _env_float("VIDEO_ACTIVE_BIN_DELTA_DB", 4.0)
VIDEO_ACTIVE_RATIO = _env_float("VIDEO_ACTIVE_RATIO", 0.35)
VIDEO_MEAN_EXCESS_DB = _env_float("VIDEO_MEAN_EXCESS_DB", 3.0)
VIDEO_OCCUPIED_BW_MHZ = _env_float("VIDEO_OCCUPIED_BW_MHZ", 0.6)
VIDEO_MAX_NARROW_PEAK_DELTA_DB = _env_float("VIDEO_MAX_NARROW_PEAK_DELTA_DB", 18.0)
VIDEO_CONFIRM_CYCLES = _env_int("VIDEO_CONFIRM_CYCLES", 2)
THREAT_EMA_ALPHA = _env_float("THREAT_EMA_ALPHA", 0.35)
WARNING_ON_LEVEL = _env_float("WARNING_ON_LEVEL", 55.0)
WARNING_OFF_LEVEL = _env_float("WARNING_OFF_LEVEL", 47.0)
CRITICAL_ON_LEVEL = _env_float("CRITICAL_ON_LEVEL", 80.0)
CRITICAL_OFF_LEVEL = _env_float("CRITICAL_OFF_LEVEL", 72.0)
STATUS_CONFIRM_CYCLES = _env_int("STATUS_CONFIRM_CYCLES", 2)

NARROWBAND_BANDS = {
    "868_870": {
        "key": "narrowband_868_870",
        "start_hz": NARROWBAND_868_870_START_HZ,
        "stop_hz": NARROWBAND_868_870_STOP_HZ,
        "center_hz": NARROWBAND_868_870_CENTER_HZ,
        "detector_type": "elrs_peak_events",
    },
    "1279_1281": {
        "key": "narrowband_1279_1281",
        "start_hz": NARROWBAND_1279_1281_START_HZ,
        "stop_hz": NARROWBAND_1279_1281_STOP_HZ,
        "center_hz": NARROWBAND_1279_1281_CENTER_HZ,
        "detector_type": "wideband_video",
    },
}


def _normalize_narrowband_band_name(value):
    normalized = str(value).strip().lower().replace("mhz", "")
    normalized = normalized.replace(" ", "").replace("-", "_")
    aliases = {
        "868": "868_870",
        "868_870": "868_870",
        "1279_1281": "1279_1281",
        "1280": "1279_1281",
    }
    return aliases.get(normalized, normalized)


def _load_enabled_narrowband_bands():
    raw = os.getenv("NARROWBAND_ENABLED_BANDS")
    if not raw:
        return NARROWBAND_BANDS

    enabled = {}
    unknown = []
    for item in raw.replace(";", ",").split(","):
        if not item.strip():
            continue
        band_name = _normalize_narrowband_band_name(item)
        if band_name in NARROWBAND_BANDS:
            enabled[band_name] = NARROWBAND_BANDS[band_name]
        else:
            unknown.append(item.strip())

    if unknown:
        allowed = ", ".join(NARROWBAND_BANDS.keys())
        raise RuntimeError(
            f"Неизвестные NARROWBAND_ENABLED_BANDS: {', '.join(unknown)}. "
            f"Допустимо: {allowed}"
        )

    if not enabled:
        raise RuntimeError("NARROWBAND_ENABLED_BANDS должен содержать хотя бы один диапазон")

    return enabled


ACTIVE_NARROWBAND_BANDS = _load_enabled_narrowband_bands()

try:
    from rtlsdr import RtlSdr
    import rtlsdr.rtlsdr as rtlsdr_module

    rtlsdr_module.RtlSdr.DEFAULT_FC = 100000000
    HAVE_SDR = True
    print(f"[init] pyrtlsdr загружен, DEFAULT_FC={rtlsdr_module.RtlSdr.DEFAULT_FC / 1e6:.1f} MHz")
except ImportError as exc:
    HAVE_SDR = False
    print(f"[init] pyrtlsdr недоступен: {exc}")
except Exception as exc:
    HAVE_SDR = False
    print(f"[init] Ошибка инициализации SDR: {exc}")


def _device_index_value():
    try:
        return int(RTLSDR_DEVICE_INDEX)
    except ValueError:
        return RTLSDR_DEVICE_INDEX


def _configure_sdr(sdr):
    sdr.sample_rate = SAMPLE_RATE
    sdr.center_freq = CENTER_FREQ
    _set_scan_gain(sdr, CENTER_FREQ)
    return sdr


def _set_scan_gain(sdr, center_freq_hz):
    use_narrowband_gain = NARROWBAND_USE_FIXED_GAIN and any(
        band["start_hz"] <= center_freq_hz <= band["stop_hz"]
        for band in ACTIVE_NARROWBAND_BANDS.values()
    )

    if use_narrowband_gain:
        sdr.gain = float(NARROWBAND_GAIN)
        return

    if GAIN.strip().lower() == "auto":
        sdr.gain = "auto"
    else:
        sdr.gain = float(GAIN)


def try_init_sdr():
    if not HAVE_SDR:
        print("[sdr] Реальное устройство недоступно")
        return None

    try:
        if SDR_MODE == "rtl_tcp":
            device_index = f"rtl_tcp://{RTL_TCP_HOST}:{RTL_TCP_PORT}"
            print(f"[sdr] Подключение к rtl_tcp {RTL_TCP_HOST}:{RTL_TCP_PORT}")
            sdr = RtlSdr(device_index=device_index)
        else:
            device_index = _device_index_value()
            print(f"[sdr] Подключение к локальному RTL-SDR, индекс {device_index}")
            sdr = RtlSdr(device_index=device_index)

        _configure_sdr(sdr)
        print(
            f"[sdr] Устройство готово: F={sdr.center_freq / 1e6:.3f} MHz, "
            f"SR={sdr.sample_rate / 1e6:.3f} MHz, Gain={sdr.gain}"
        )
        return sdr
    except Exception as exc:
        import traceback

        print(f"[sdr] Не удалось подключить SDR: {exc}")
        traceback.print_exc()
        return None


def send_telegram_alert(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }
        requests.post(url, json=payload, timeout=2)
    except Exception as exc:
        print(f"[notify] Ошибка отправки Telegram: {exc}")


def send_notification_alert(level, dominant_freq_hz, detection=None):
    if not NOTIFICATION_API_URL:
        return False

    details = {
        "device_id": DEVICE_ID,
        "advice": "Спрячьтесь в укрытие",
    }
    if detection:
        details.update(detection.get("details", {}))
        if detection.get("reason"):
            details["reason"] = detection["reason"]

    payload = {
        "source": "rf",
        "title": "ТРЕВОГА! ОБНАРУЖЕН ДРОН!",
        "level": round(float(level), 2),
        "frequency_mhz": round(float(dominant_freq_hz) / 1e6, 3),
        "details": details,
    }

    try:
        response = requests.post(NOTIFICATION_API_URL, json=payload, timeout=2)
        response.raise_for_status()
        result = response.json()
        if result.get("accepted"):
            print("[notify] RF alert отправлен в Notification Gateway")
        else:
            print(f"[notify] Notification Gateway: {result.get('reason', result)}")
        return True
    except Exception as exc:
        print(f"[notify] Ошибка отправки в Notification Gateway: {exc}")
        return False


def _read_rf_level(samples):
    power = np.mean(np.abs(samples) ** 2)
    rf_db = 10 * np.log10(power + 1e-9)
    noise_floor_db = -60.0
    max_signal_db = -10.0
    rf_level_scaled = (rf_db - noise_floor_db) * (100 / (max_signal_db - noise_floor_db))
    return max(2.0, min(100.0, rf_level_scaled))


def _capture_center_freq(current_freq):
    for band in ACTIVE_NARROWBAND_BANDS.values():
        if band["start_hz"] <= current_freq <= band["stop_hz"]:
            return band["center_hz"]
    return current_freq


def _get_narrowband_by_center_freq(center_freq_hz):
    for band in ACTIVE_NARROWBAND_BANDS.values():
        if abs(center_freq_hz - band["center_hz"]) < 1:
            return band
    return None


def _compute_narrowband_spectrum(samples, center_freq_hz, band):
    if not band:
        return None

    fft_size = min(NARROWBAND_FFT_SIZE, len(samples))
    if fft_size < 1024:
        return None

    window = np.hanning(fft_size)
    step = max(fft_size // 2, 1)
    spectrum_sum = None
    segment_count = 0

    for start in range(0, len(samples) - fft_size + 1, step):
        segment = samples[start:start + fft_size]
        weighted = segment * window
        spectrum = np.fft.fftshift(np.fft.fft(weighted, n=fft_size))
        psd = (np.abs(spectrum) ** 2) / (np.sum(window ** 2) + 1e-12)
        if spectrum_sum is None:
            spectrum_sum = psd
        else:
            spectrum_sum += psd
        segment_count += 1

    if spectrum_sum is None or segment_count == 0:
        return None

    mean_psd = spectrum_sum / segment_count
    spectrum_dbm = 10 * np.log10(mean_psd + 1e-12) + NARROWBAND_DBM_OFFSET
    freqs_hz = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1 / SAMPLE_RATE)) + center_freq_hz

    mask = (freqs_hz >= band["start_hz"]) & (freqs_hz <= band["stop_hz"])
    if not np.any(mask):
        return None

    narrow_freqs = freqs_hz[mask] / 1e6
    narrow_power = spectrum_dbm[mask]
    target_freqs = np.linspace(band["start_hz"] / 1e6, band["stop_hz"] / 1e6, NARROWBAND_POINTS)
    target_power = np.interp(target_freqs, narrow_freqs, narrow_power)
    noise_floor_dbm = float(np.percentile(target_power, 35))
    peak_index = int(np.argmax(target_power))
    peak_power_dbm = float(target_power[peak_index])
    peak_freq_mhz = float(target_freqs[peak_index])
    peak_delta_db = peak_power_dbm - noise_floor_dbm
    peak_detected = peak_delta_db >= NARROWBAND_PEAK_DELTA_DB
    active_threshold_dbm = noise_floor_dbm + VIDEO_ACTIVE_BIN_DELTA_DB
    active_mask = target_power >= active_threshold_dbm
    active_ratio = float(np.count_nonzero(active_mask) / max(len(target_power), 1))
    occupied_bw_mhz = active_ratio * ((band["stop_hz"] - band["start_hz"]) / 1e6)
    if np.any(active_mask):
        mean_excess_db = float(np.mean(target_power[active_mask] - noise_floor_dbm))
    else:
        mean_excess_db = 0.0

    return {
        "start_mhz": round(band["start_hz"] / 1e6, 3),
        "stop_mhz": round(band["stop_hz"] / 1e6, 3),
        "freqs_mhz": [round(value, 4) for value in target_freqs.tolist()],
        "bins": [round(value, 2) for value in target_power.tolist()],
        "peak_detected": peak_detected,
        "peak_freq_mhz": round(peak_freq_mhz, 4),
        "peak_power_dbm": round(peak_power_dbm, 2),
        "noise_floor_dbm": round(noise_floor_dbm, 2),
        "peak_delta_db": round(peak_delta_db, 2),
        "active_ratio": round(active_ratio, 3),
        "occupied_bw_mhz": round(occupied_bw_mhz, 3),
        "mean_excess_db": round(mean_excess_db, 2),
    }


def _smooth_narrowband_spectrum(current_spectrum, previous_spectrum):
    if not current_spectrum or not previous_spectrum:
        return current_spectrum

    current_bins = np.asarray(current_spectrum.get("bins", []), dtype=float)
    previous_bins = np.asarray(previous_spectrum.get("bins", []), dtype=float)
    if len(current_bins) != len(previous_bins):
        return current_spectrum

    alpha = max(0.0, min(1.0, NARROWBAND_SMOOTHING_ALPHA))
    smoothed_bins = previous_bins * (1.0 - alpha) + current_bins * alpha
    current_spectrum["bins"] = [round(value, 2) for value in smoothed_bins.tolist()]

    noise_floor_dbm = float(np.percentile(smoothed_bins, 35))
    peak_index = int(np.argmax(smoothed_bins))
    peak_power_dbm = float(smoothed_bins[peak_index])
    peak_delta_db = peak_power_dbm - noise_floor_dbm
    current_spectrum["noise_floor_dbm"] = round(noise_floor_dbm, 2)
    current_spectrum["peak_power_dbm"] = round(peak_power_dbm, 2)
    current_spectrum["peak_freq_mhz"] = current_spectrum["freqs_mhz"][peak_index]
    current_spectrum["peak_delta_db"] = round(peak_delta_db, 2)
    current_spectrum["peak_detected"] = peak_delta_db >= NARROWBAND_PEAK_DELTA_DB
    active_threshold_dbm = noise_floor_dbm + VIDEO_ACTIVE_BIN_DELTA_DB
    active_mask = smoothed_bins >= active_threshold_dbm
    active_ratio = float(np.count_nonzero(active_mask) / max(len(smoothed_bins), 1))
    start_mhz = float(current_spectrum.get("start_mhz", 0.0))
    stop_mhz = float(current_spectrum.get("stop_mhz", start_mhz))
    current_spectrum["active_ratio"] = round(active_ratio, 3)
    current_spectrum["occupied_bw_mhz"] = round(active_ratio * max(0.0, stop_mhz - start_mhz), 3)
    if np.any(active_mask):
        current_spectrum["mean_excess_db"] = round(float(np.mean(smoothed_bins[active_mask] - noise_floor_dbm)), 2)
    else:
        current_spectrum["mean_excess_db"] = 0.0
    return current_spectrum


def _refresh_single_narrowband_spectrum(sdr, last_narrowband, band_name):
    band = NARROWBAND_BANDS[band_name]
    try:
        sdr.center_freq = band["center_hz"]
        _set_scan_gain(sdr, band["center_hz"])
        samples = sdr.read_samples(NARROWBAND_CAPTURE_SIZE)
        narrowband_spectrum = _compute_narrowband_spectrum(samples, band["center_hz"], band)
        if narrowband_spectrum is not None:
            last_narrowband[band_name] = _smooth_narrowband_spectrum(
                narrowband_spectrum,
                last_narrowband[band_name],
            )
    except Exception as exc:
        print(f"[sdr] Узкополосный спектр {band['start_hz'] / 1e6:.1f}-{band['stop_hz'] / 1e6:.1f} MHz недоступен: {exc}")

    return last_narrowband


def _build_spectrum_preview(spectrum_memory):
    spectrum_preview = []
    for channel in SCAN_CHANNELS:
        level = spectrum_memory.get(channel["freq"], 0.0)
        spectrum_preview.append(round(max(0.0, level), 2))
    return spectrum_preview


def _detect_status(rf_level):
    if rf_level > 80:
        return "CRITICAL"
    if rf_level > 50:
        return "WARNING"
    return "OK"


def _compute_cycle_level(cycle_levels):
    if not cycle_levels:
        return 0.0, CENTER_FREQ

    ordered = sorted(cycle_levels.items(), key=lambda item: item[1], reverse=True)
    dominant_freq, peak_level = ordered[0]
    return peak_level, dominant_freq


def _new_detection_state():
    return {
        band_name: {"events": [], "confirm_count": 0}
        for band_name in NARROWBAND_BANDS
    }


def _active_cluster_width_mhz(freqs_mhz, power_dbm, peak_freq_mhz, threshold_dbm):
    freqs = np.asarray(freqs_mhz, dtype=float)
    power = np.asarray(power_dbm, dtype=float)
    if len(freqs) < 2 or len(freqs) != len(power):
        return 0.0, 0

    peak_index = int(np.argmin(np.abs(freqs - peak_freq_mhz)))
    if power[peak_index] < threshold_dbm:
        return 0.0, 0

    left = peak_index
    while left > 0 and power[left - 1] >= threshold_dbm:
        left -= 1

    right = peak_index
    while right < len(power) - 1 and power[right + 1] >= threshold_dbm:
        right += 1

    bin_step_mhz = float(np.median(np.diff(freqs)))
    active_bins = right - left + 1
    width_mhz = max(bin_step_mhz, (freqs[right] - freqs[left]) + bin_step_mhz)
    return float(width_mhz), int(active_bins)


def _detect_elrs_activity(spectrum, state):
    now = time.monotonic()
    window_seconds = max(1.0, ELRS_EVENT_WINDOW_SECONDS)
    events = [event_at for event_at in state.get("events", []) if now - event_at <= window_seconds]
    peak_delta_db = float(spectrum.get("peak_delta_db") or 0.0)
    peak_power_dbm = float(spectrum.get("peak_power_dbm") or -999.0)
    noise_floor_dbm = float(spectrum.get("noise_floor_dbm") or -999.0)
    peak_freq_mhz = float(spectrum.get("peak_freq_mhz") or 0.0)
    strong_enough = peak_power_dbm >= ELRS_MIN_PEAK_POWER_DBM
    cluster_width_mhz, cluster_bins = _active_cluster_width_mhz(
        spectrum.get("freqs_mhz", []),
        spectrum.get("bins", []),
        peak_freq_mhz,
        noise_floor_dbm + ELRS_ACTIVE_BIN_DELTA_DB,
    )
    wide_enough = (
        cluster_width_mhz >= ELRS_MIN_OCCUPIED_BW_MHZ
        and cluster_bins >= ELRS_MIN_ACTIVE_BINS
    )

    if strong_enough and wide_enough and peak_delta_db >= ELRS_NORMAL_PEAK_DELTA_DB:
        events.append(now)

    state["events"] = events
    event_count = len(events)
    strong_peak = strong_enough and wide_enough and peak_delta_db >= ELRS_STRONG_PEAK_DELTA_DB
    critical = (ELRS_STRONG_PEAK_IMMEDIATE and strong_peak) or event_count >= ELRS_CRITICAL_EVENTS
    warning = critical or event_count >= ELRS_WARNING_EVENTS

    if critical:
        status = "CRITICAL"
        threat_level = NARROWBAND_PEAK_THREAT_LEVEL
    elif warning:
        status = "WARNING"
        threat_level = WARNING_ON_LEVEL
    else:
        status = "OK"
        threat_level = 0.0

    return {
        "detected": status != "OK",
        "status": status,
        "threat_level": threat_level,
        "frequency_hz": peak_freq_mhz * 1e6 if peak_freq_mhz > 0 else NARROWBAND_868_870_CENTER_HZ,
        "reason": (
            f"elrs peak_delta={peak_delta_db:.1f}dB peak={peak_power_dbm:.1f}dBm "
            f"width={cluster_width_mhz:.3f}MHz bins={cluster_bins} "
            f"events={event_count}/{window_seconds:.0f}s strong={strong_peak}"
        ),
        "details": {
            "detector": "elrs_peak_events",
            "peak_delta_db": round(peak_delta_db, 2),
            "peak_power_dbm": round(peak_power_dbm, 2),
            "cluster_width_mhz": round(cluster_width_mhz, 3),
            "cluster_bins": cluster_bins,
            "min_occupied_bw_mhz": round(ELRS_MIN_OCCUPIED_BW_MHZ, 3),
            "min_active_bins": ELRS_MIN_ACTIVE_BINS,
            "events": event_count,
            "window_seconds": round(window_seconds, 1),
            "min_peak_power_dbm": round(ELRS_MIN_PEAK_POWER_DBM, 2),
            "strong_peak_immediate": ELRS_STRONG_PEAK_IMMEDIATE,
        },
    }


def _detect_wideband_video_activity(spectrum, state):
    active_ratio = float(spectrum.get("active_ratio") or 0.0)
    occupied_bw_mhz = float(spectrum.get("occupied_bw_mhz") or 0.0)
    mean_excess_db = float(spectrum.get("mean_excess_db") or 0.0)
    peak_delta_db = float(spectrum.get("peak_delta_db") or 0.0)
    peak_freq_mhz = float(spectrum.get("peak_freq_mhz") or 0.0)

    wide_enough = (
        active_ratio >= VIDEO_ACTIVE_RATIO
        and occupied_bw_mhz >= VIDEO_OCCUPIED_BW_MHZ
        and mean_excess_db >= VIDEO_MEAN_EXCESS_DB
    )
    not_just_tone = peak_delta_db <= VIDEO_MAX_NARROW_PEAK_DELTA_DB or active_ratio >= 0.65
    candidate = wide_enough and not_just_tone

    if candidate:
        state["confirm_count"] = state.get("confirm_count", 0) + 1
    else:
        state["confirm_count"] = max(0, state.get("confirm_count", 0) - 1)

    confirm_count = state["confirm_count"]
    critical = confirm_count >= max(1, VIDEO_CONFIRM_CYCLES)
    warning = critical or confirm_count > 0

    if critical:
        status = "CRITICAL"
        threat_level = NARROWBAND_PEAK_THREAT_LEVEL
    elif warning:
        status = "WARNING"
        threat_level = WARNING_ON_LEVEL
    else:
        status = "OK"
        threat_level = 0.0

    return {
        "detected": status != "OK",
        "status": status,
        "threat_level": threat_level,
        "frequency_hz": peak_freq_mhz * 1e6 if peak_freq_mhz > 0 else NARROWBAND_1279_1281_CENTER_HZ,
        "reason": (
            f"video active_ratio={active_ratio:.2f} occupied_bw={occupied_bw_mhz:.2f}MHz "
            f"mean_excess={mean_excess_db:.1f}dB peak_delta={peak_delta_db:.1f}dB "
            f"confirm={confirm_count}/{VIDEO_CONFIRM_CYCLES}"
        ),
        "details": {
            "detector": "wideband_video",
            "active_ratio": round(active_ratio, 3),
            "occupied_bw_mhz": round(occupied_bw_mhz, 3),
            "mean_excess_db": round(mean_excess_db, 2),
            "peak_delta_db": round(peak_delta_db, 2),
            "confirm_count": confirm_count,
        },
    }


def _detect_band_activity(band_name, spectrum, state):
    detector_type = NARROWBAND_BANDS[band_name].get("detector_type")
    if detector_type == "elrs_peak_events":
        return _detect_elrs_activity(spectrum, state)
    if detector_type == "wideband_video":
        return _detect_wideband_video_activity(spectrum, state)
    return {"detected": False, "status": "OK", "threat_level": 0.0, "frequency_hz": CENTER_FREQ, "reason": "disabled", "details": {}}


def _stronger_detection(current, candidate):
    if not candidate or not candidate.get("detected"):
        return current
    if current is None:
        return candidate
    rank = {"OK": 0, "WARNING": 1, "CRITICAL": 2}
    if rank.get(candidate.get("status", "OK"), 0) > rank.get(current.get("status", "OK"), 0):
        return candidate
    if candidate.get("threat_level", 0.0) > current.get("threat_level", 0.0):
        return candidate
    return current


def _smooth_threat_level(previous_level, current_level):
    if previous_level is None:
        return current_level

    alpha = max(0.0, min(1.0, THREAT_EMA_ALPHA))
    return previous_level * (1.0 - alpha) + current_level * alpha


def _build_critical_alert_message(level, dominant_freq_hz):
    return (
        "🚨 *ТРЕВОГА! ОБНАРУЖЕН ДРОН!* 🚨\n\n"
        f"Уровень сигнала: *{level:.1f}*% 📈\n"
        f"Диапазон: {dominant_freq_hz / 1e6:.3f} MHz\n"
        "Совет: Спрячтесь в укрытие!"
    )


def _next_stable_status(current_status, stable_level, pending_cycles):
    if current_status == "CRITICAL":
        if stable_level <= CRITICAL_OFF_LEVEL:
            pending_cycles += 1
            if pending_cycles >= STATUS_CONFIRM_CYCLES:
                return "WARNING", 0
            return current_status, pending_cycles
        return current_status, 0

    if current_status == "WARNING":
        if stable_level >= CRITICAL_ON_LEVEL:
            pending_cycles += 1
            if pending_cycles >= STATUS_CONFIRM_CYCLES:
                return "CRITICAL", 0
            return current_status, pending_cycles
        if stable_level <= WARNING_OFF_LEVEL:
            pending_cycles += 1
            if pending_cycles >= STATUS_CONFIRM_CYCLES:
                return "OK", 0
            return current_status, pending_cycles
        return current_status, 0

    if stable_level >= CRITICAL_ON_LEVEL:
        pending_cycles += 1
        if pending_cycles >= STATUS_CONFIRM_CYCLES:
            return "CRITICAL", 0
        return current_status, pending_cycles
    if stable_level >= WARNING_ON_LEVEL:
        pending_cycles += 1
        if pending_cycles >= STATUS_CONFIRM_CYCLES:
            return "WARNING", 0
        return current_status, pending_cycles
    return current_status, 0


def main():
    sdr = try_init_sdr()
    print(
        f"[main] Старт сканирования: channels={len(SCAN_CHANNELS)}, "
        f"narrowband={','.join(ACTIVE_NARROWBAND_BANDS.keys())}, "
        f"mode={SDR_MODE if sdr else 'waiting-for-sdr'}, api={API_URL}, device={DEVICE_ID}"
    )

    last_status = "OK"
    channel_idx = 0
    spectrum_memory = {channel["freq"]: 5.0 for channel in SCAN_CHANNELS}
    last_narrowband = {
        band_name: None for band_name in NARROWBAND_BANDS
    }
    cycle_levels = {}
    stable_level = 0.0
    last_cycle_level = None
    last_gateway_alert_at = 0.0
    last_telemetry_post_at = 0.0
    stable_dominant_freq = CENTER_FREQ
    status_pending_cycles = 0
    narrowband_cycle = list(ACTIVE_NARROWBAND_BANDS.keys())
    narrowband_cycle_idx = 0
    detection_state = _new_detection_state()
    cycle_detection = None
    last_alert_detection = None

    try:
        while True:
            current_channel = SCAN_CHANNELS[channel_idx]
            current_freq = current_channel["freq"]
            current_name = current_channel["name"]
            channel_idx = (channel_idx + 1) % len(SCAN_CHANNELS)

            try:
                if not HAVE_SDR:
                    print("[sdr] pyrtlsdr недоступен, ожидание исправного окружения")
                    time.sleep(5)
                    continue

                if sdr is None:
                    print("[sdr] SDR не подключен, повторная попытка через 2 секунды")
                    time.sleep(2)
                    sdr = try_init_sdr()
                    continue

                tuned_center_freq = _capture_center_freq(current_freq)
                sdr.center_freq = tuned_center_freq
                _set_scan_gain(sdr, tuned_center_freq)
                narrowband_band = _get_narrowband_by_center_freq(tuned_center_freq)
                narrowband_band_name = None
                sample_count = NARROWBAND_CAPTURE_SIZE if narrowband_band else READ_SIZE
                samples = sdr.read_samples(sample_count)
                rf_level = _read_rf_level(samples)
                if narrowband_band is not None:
                    narrowband_band_name = next(name for name, band in ACTIVE_NARROWBAND_BANDS.items() if band is narrowband_band)
                    narrowband_spectrum = _compute_narrowband_spectrum(samples, tuned_center_freq, narrowband_band)
                    if narrowband_spectrum is not None:
                        smoothed_spectrum = _smooth_narrowband_spectrum(
                            narrowband_spectrum,
                            last_narrowband[narrowband_band_name],
                        )
                        last_narrowband[narrowband_band_name] = smoothed_spectrum
                        detection = _detect_band_activity(
                            narrowband_band_name,
                            smoothed_spectrum,
                            detection_state[narrowband_band_name],
                        )
                        if detection.get("detected"):
                            cycle_detection = _stronger_detection(cycle_detection, detection)
                            rf_level = max(rf_level, detection.get("threat_level", 0.0))
                            print(
                                f"[detect] {narrowband_band_name} {detection.get('status')} "
                                f"{detection.get('reason')}"
                            )

                if NARROWBAND_EXTRA_REFRESH:
                    refresh_band_name = narrowband_cycle[narrowband_cycle_idx]
                    narrowband_cycle_idx = (narrowband_cycle_idx + 1) % len(narrowband_cycle)
                    if refresh_band_name != narrowband_band_name:
                        last_narrowband = _refresh_single_narrowband_spectrum(
                            sdr,
                            last_narrowband,
                            refresh_band_name,
                        )
            except Exception as exc:
                print(f"[sdr] Ошибка чтения: {exc}")
                if sdr:
                    print("[sdr] Потеря связи с SDR, выполняю сброс")
                    try:
                        sdr.close()
                    except Exception:
                        pass
                    sdr = None
                time.sleep(1)
                continue

            spectrum_memory[current_freq] = rf_level
            cycle_levels[current_freq] = rf_level
            spectrum_preview = _build_spectrum_preview(spectrum_memory)

            if len(cycle_levels) >= len(SCAN_CHANNELS):
                cycle_level, dominant_freq = _compute_cycle_level(cycle_levels)
                last_cycle_level = cycle_level
                if cycle_detection and cycle_detection.get("status") == "CRITICAL":
                    stable_level = max(cycle_level, cycle_detection.get("threat_level", CRITICAL_ON_LEVEL), CRITICAL_ON_LEVEL)
                    stable_dominant_freq = cycle_detection.get("frequency_hz", dominant_freq)
                    next_status = "CRITICAL"
                    last_alert_detection = cycle_detection
                    status_pending_cycles = 0
                elif cycle_detection and cycle_detection.get("status") == "WARNING":
                    stable_level = max(cycle_level, cycle_detection.get("threat_level", WARNING_ON_LEVEL), WARNING_ON_LEVEL)
                    stable_dominant_freq = cycle_detection.get("frequency_hz", dominant_freq)
                    next_status = "WARNING"
                    status_pending_cycles = 0
                else:
                    stable_level = _smooth_threat_level(stable_level if stable_level > 0 else None, cycle_level)
                    stable_dominant_freq = dominant_freq
                    next_status, status_pending_cycles = _next_stable_status(
                        last_status,
                        stable_level,
                        status_pending_cycles,
                    )
                cycle_levels = {}
                cycle_detection = None
            else:
                next_status = last_status

            status = next_status

            if status != last_status:
                if status == "CRITICAL":
                    msg = _build_critical_alert_message(stable_level, stable_dominant_freq)
                    print("[notify] Отправляю ALERT в Telegram")
                    send_telegram_alert(msg)
                elif status == "WARNING" and last_status == "CRITICAL":
                    msg = (
                        "⚠️ *УРОВЕНЬ УГРОЗЫ СНИЗИЛСЯ*\n\n"
                        "Статус: ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ\n"
                        f"Уровень сигнала: {stable_level:.1f}%\n"
                        "Оставайтесь бдительны."
                    )
                    print("[notify] Отправляю уведомление о снижении угрозы")
                    send_telegram_alert(msg)
                elif status == "OK":
                    if last_status == "CRITICAL":
                        msg = f"✅ *УГРОЗА МИНОВАЛА*\n\nЭфир чист. Уровень сигнала: {stable_level:.1f}%"
                    elif last_status == "WARNING":
                        msg = (
                            "✅ *ВСЁ СПОКОЙНО*\n\n"
                            "Подозрительная активность прекратилась.\n"
                            f"Уровень сигнала: {stable_level:.1f}%"
                        )
                    else:
                        msg = None

                    if msg:
                        print("[notify] Отправляю сообщение 'Отбой'")
                        send_telegram_alert(msg)

                last_status = status

            if NOTIFICATION_API_URL and stable_level >= CRITICAL_ON_LEVEL:
                now = time.time()
                retry_seconds = max(0.0, NOTIFICATION_GATEWAY_RETRY_SECONDS)
                if last_gateway_alert_at <= 0.0 or now - last_gateway_alert_at >= retry_seconds:
                    print("[notify] Отправляю RF alert в Notification Gateway")
                    if send_notification_alert(stable_level, stable_dominant_freq, last_alert_detection):
                        last_gateway_alert_at = now

            now = time.monotonic()
            if (
                TELEMETRY_POST_INTERVAL_SECONDS > 0
                and now - last_telemetry_post_at < TELEMETRY_POST_INTERVAL_SECONDS
            ):
                continue
            last_telemetry_post_at = now

            spectrum_payload = {"bins": spectrum_preview}
            for band_name, band in ACTIVE_NARROWBAND_BANDS.items():
                spectrum_payload[band["key"]] = last_narrowband.get(band_name)

            payload = {
                "device_id": DEVICE_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "metrics": {
                    "velocity_rms_mm_s": round(float(stable_level), 2),
                    "accel_peak_g": 0.0,
                    "crest_factor": 1.0,
                    "temperature_c": 40.0,
                    "dominant_freq_hz": stable_dominant_freq / 1e6,
                },
                "spectrum": spectrum_payload,
            }

            try:
                response = requests.post(API_URL, json=payload, timeout=2)
                if response.status_code == 201:
                    print(
                        f"[tx] [SDR] live={rf_level:.1f} cycle={last_cycle_level if last_cycle_level is not None else 0:.1f} "
                        f"stable={stable_level:.1f} status={status} freq={stable_dominant_freq / 1e6:.3f} MHz"
                    )
                else:
                    print(f"[tx] backend вернул {response.status_code}: {response.text[:200]}")
            except Exception as exc:
                print(f"[tx] Ошибка сети: {exc}")

    except KeyboardInterrupt:
        if sdr:
            sdr.close()
        print("\n[main] Остановка")


if __name__ == "__main__":
    main()