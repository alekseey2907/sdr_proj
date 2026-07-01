"""
RF Event Analyzer - Command Line Interface
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from rf_analyzer.core.config import AppConfig, DeviceType, FrequencyRange
from rf_analyzer.engine.monitor import RFMonitor, MonitorState
from rf_analyzer.license.license_manager import LicenseManager
from rf_analyzer.reports.generator import ReportGenerator
from rf_analyzer.storage.event_storage import EventStorage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def cmd_monitor(args: argparse.Namespace) -> int:
    """Команда мониторинга"""
    config_path = Path(args.config)
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return 1
    
    # Проверка лицензии
    license_mgr = LicenseManager()
    if not license_mgr.is_licensed():
        status = license_mgr.get_status()
        logger.error(f"License: {status['message']}")
        logger.info("Run 'rf-analyzer license --start-trial' to start trial")
        return 1
    
    # Загружаем конфиг
    config = AppConfig.load(config_path)
    
    # Проверяем лимит диапазонов
    license_info = license_mgr.get_license()
    enabled_ranges = [r for r in config.ranges if r.enabled]
    if not license_mgr.can_add_range(len(enabled_ranges) - 1):
        logger.error(
            f"License limit: max {license_info.max_ranges} ranges, "
            f"configured {len(enabled_ranges)}"
        )
        return 1
    
    # Создаём хранилище
    storage = EventStorage(config.output.database_path)
    
    # Callback для событий
    def on_event(event):
        freq_mhz = event.center_freq / 1e6
        print(
            f"[EVENT] {event.start_time.strftime('%H:%M:%S')} | "
            f"{event.range_name} | {freq_mhz:.3f} MHz | "
            f"{event.max_power_db:.1f} dB | {event.event_type.value}"
        )
    
    # Создаём монитор
    monitor = RFMonitor(config, storage, on_event=on_event)
    
    print(f"Starting RF monitor with {len(enabled_ranges)} range(s)...")
    print("Press Ctrl+C to stop\n")
    
    if not monitor.start():
        logger.error("Failed to start monitor")
        return 1
    
    try:
        import time
        while monitor.state == MonitorState.RUNNING:
            time.sleep(5)
            stats = monitor.get_stats()
            print(
                f"\r[STATS] Uptime: {stats.uptime_seconds:.0f}s | "
                f"Spectrums: {stats.total_spectrums} | "
                f"Events: {stats.events_detected} | "
                f"Range: {stats.current_range}",
                end="", flush=True
            )
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        monitor.stop()
    
    print(f"\nMonitor stopped. Total events: {monitor.get_stats().events_detected}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Команда генерации отчёта"""
    # Проверка лицензии
    license_mgr = LicenseManager()
    if not license_mgr.is_licensed():
        status = license_mgr.get_status()
        logger.error(f"License: {status['message']}")
        return 1
    
    if not license_mgr.can_generate_report():
        license_info = license_mgr.get_license()
        logger.error(
            f"Daily report limit reached ({license_info.max_reports_per_day}). "
            "Upgrade to Pro for unlimited reports."
        )
        return 1
    
    # Парсим даты
    try:
        if args.from_date:
            start_time = datetime.strptime(args.from_date, "%Y-%m-%d")
        else:
            start_time = datetime.now() - timedelta(days=1)
        
        if args.to_date:
            end_time = datetime.strptime(args.to_date, "%Y-%m-%d")
            end_time = end_time.replace(hour=23, minute=59, second=59)
        else:
            end_time = datetime.now()
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return 1
    
    # База данных
    db_path = Path(args.database) if args.database else Path("events.db")
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1
    
    storage = EventStorage(db_path)
    generator = ReportGenerator(storage)
    
    # Путь вывода
    output_path = Path(args.output) if args.output else Path(f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    # Генерируем отчёт
    title = args.title or "Отчёт о RF-событиях"
    range_names = args.ranges.split(",") if args.ranges else None
    
    print(f"Generating report: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    
    try:
        if args.format == "pdf":
            output_path = output_path.with_suffix(".pdf")
            generator.generate_pdf_report(start_time, end_time, output_path, title, range_names)
        elif args.format == "csv":
            output_path = output_path.with_suffix(".csv")
            generator.generate_csv_report(start_time, end_time, output_path, range_names)
        else:  # html
            output_path = output_path.with_suffix(".html")
            generator.save_html_report(start_time, end_time, output_path, title, range_names)
        
        # Записываем использование
        license_mgr.record_report_generated()
        
        print(f"Report saved: {output_path}")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return 1


def cmd_events(args: argparse.Namespace) -> int:
    """Команда просмотра событий"""
    db_path = Path(args.database) if args.database else Path("events.db")
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1
    
    storage = EventStorage(db_path)
    
    # Определяем период
    if args.last:
        # Парсим формат: 24h, 7d, etc.
        value = args.last[:-1]
        unit = args.last[-1]
        
        if unit == 'h':
            start_time = datetime.now() - timedelta(hours=int(value))
        elif unit == 'd':
            start_time = datetime.now() - timedelta(days=int(value))
        else:
            logger.error(f"Invalid time format: {args.last}")
            return 1
        
        end_time = datetime.now()
    else:
        start_time = None
        end_time = None
    
    # Получаем события
    events = storage.get_events(
        start_time=start_time,
        end_time=end_time,
        range_name=args.range,
        limit=args.limit
    )
    
    if args.json:
        # JSON вывод
        data = [e.to_dict() for e in events]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        # Табличный вывод
        print(f"\n{'ID':>6} | {'Time':^19} | {'Range':<20} | {'Freq (MHz)':>12} | {'Max dB':>8} | {'Type':<12}")
        print("-" * 95)
        
        for event in events:
            freq_mhz = event.center_freq / 1e6
            print(
                f"{event.id:>6} | "
                f"{event.start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"{event.range_name:<20} | "
                f"{freq_mhz:>12.3f} | "
                f"{event.max_power_db:>8.1f} | "
                f"{event.event_type.value:<12}"
            )
        
        print(f"\nTotal: {len(events)} events")
    
    return 0


def cmd_license(args: argparse.Namespace) -> int:
    """Команда управления лицензией"""
    license_mgr = LicenseManager()
    
    if args.start_trial:
        try:
            license_info = license_mgr.start_trial()
            print(f"Trial started! Expires: {license_info.expires_at.strftime('%Y-%m-%d')}")
            print(f"Limits: {license_info.max_ranges} range(s), {license_info.max_reports_per_day} report(s)/day")
            return 0
        except ValueError as e:
            logger.error(str(e))
            return 1
    
    if args.activate:
        try:
            license_info = license_mgr.activate_license(args.activate)
            print(f"License activated: {license_info.license_type.value}")
            print(f"Expires: {license_info.expires_at.strftime('%Y-%m-%d')}")
            return 0
        except ValueError as e:
            logger.error(f"Activation failed: {e}")
            return 1
    
    # Показать статус
    status = license_mgr.get_status()
    print("\nLicense Status:")
    print(f"  Status: {status['status']}")
    
    if status['status'] == 'active':
        print(f"  Type: {status['license_type']}")
        print(f"  Days remaining: {status['days_remaining']}")
        print(f"  Expires: {status['expires_at']}")
        print(f"  Max ranges: {status['max_ranges']}")
        print(f"  Reports today: {status['reports_today']}/{status['max_reports_per_day']}")
    else:
        print(f"  Message: {status.get('message', 'N/A')}")
    
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Команда создания конфигурации"""
    output_path = Path(args.output) if args.output else Path("config.yaml")
    
    if output_path.exists() and not args.force:
        logger.error(f"Config already exists: {output_path}. Use --force to overwrite.")
        return 1
    
    # Создаём дефолтный конфиг
    config = AppConfig.default()
    
    # Добавляем примеры диапазонов
    config.ranges = [
        FrequencyRange(
            name="FM Broadcast",
            start_freq=88e6,
            stop_freq=108e6,
            threshold_db=-40.0,
            min_duration_ms=1000.0,
        ),
        FrequencyRange(
            name="Air Band",
            start_freq=118e6,
            stop_freq=137e6,
            threshold_db=-60.0,
            min_duration_ms=100.0,
        ),
        FrequencyRange(
            name="ISM 433MHz",
            start_freq=433e6,
            stop_freq=434.8e6,
            threshold_db=-65.0,
            min_duration_ms=50.0,
        ),
    ]
    
    if args.simulated:
        config.device.device_type = DeviceType.SIMULATED
    
    config.save(output_path)
    print(f"Config created: {output_path}")
    print("Edit ranges and thresholds as needed.")
    
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Команда статистики"""
    db_path = Path(args.database) if args.database else Path("events.db")
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1
    
    storage = EventStorage(db_path)
    
    # Период
    start_time = None
    end_time = None
    
    if args.last:
        value = args.last[:-1]
        unit = args.last[-1]
        
        if unit == 'h':
            start_time = datetime.now() - timedelta(hours=int(value))
        elif unit == 'd':
            start_time = datetime.now() - timedelta(days=int(value))
        
        end_time = datetime.now()
    
    stats = storage.get_statistics(start_time, end_time)
    
    print("\n=== RF Event Statistics ===\n")
    print(f"Total events: {stats['total_events']}")
    print(f"Max power: {stats['max_power_db']:.1f} dB")
    print(f"Avg duration: {stats['avg_duration_ms']:.0f} ms")
    
    print("\nBy type:")
    for event_type, count in stats['by_type'].items():
        print(f"  {event_type}: {count}")
    
    print("\nBy range:")
    for range_name, count in stats['by_range'].items():
        print(f"  {range_name}: {count}")
    
    return 0


def main() -> int:
    """Главная точка входа CLI"""
    parser = argparse.ArgumentParser(
        prog="rf-analyzer",
        description="RF Event Analyzer - Professional RF monitoring tool"
    )
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 1.0.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Start RF monitoring")
    monitor_parser.add_argument("-c", "--config", default="config.yaml", help="Config file path")
    
    # report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("-f", "--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    report_parser.add_argument("-t", "--to", dest="to_date", help="End date (YYYY-MM-DD)")
    report_parser.add_argument("-o", "--output", help="Output file path")
    report_parser.add_argument("--format", choices=["pdf", "html", "csv"], default="pdf", help="Output format")
    report_parser.add_argument("--title", help="Report title")
    report_parser.add_argument("--ranges", help="Comma-separated range names")
    report_parser.add_argument("-d", "--database", help="Database path")
    
    # events command
    events_parser = subparsers.add_parser("events", help="View events")
    events_parser.add_argument("-l", "--last", help="Time period (e.g., 24h, 7d)")
    events_parser.add_argument("-r", "--range", help="Filter by range name")
    events_parser.add_argument("-n", "--limit", type=int, default=100, help="Max events")
    events_parser.add_argument("-d", "--database", help="Database path")
    events_parser.add_argument("--json", action="store_true", help="JSON output")
    
    # license command
    license_parser = subparsers.add_parser("license", help="License management")
    license_parser.add_argument("--start-trial", action="store_true", help="Start 7-day trial")
    license_parser.add_argument("--activate", metavar="KEY", help="Activate license key")
    
    # config command
    config_parser = subparsers.add_parser("config", help="Create config file")
    config_parser.add_argument("-o", "--output", help="Output path")
    config_parser.add_argument("--force", action="store_true", help="Overwrite existing")
    config_parser.add_argument("--simulated", action="store_true", help="Use simulated device")
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("-l", "--last", help="Time period (e.g., 24h, 7d)")
    stats_parser.add_argument("-d", "--database", help="Database path")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    commands = {
        "monitor": cmd_monitor,
        "report": cmd_report,
        "events": cmd_events,
        "license": cmd_license,
        "config": cmd_config,
        "stats": cmd_stats,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
