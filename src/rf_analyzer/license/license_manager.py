"""
RF Event Analyzer - License Manager
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LicenseType(Enum):
    TRIAL = "trial"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LicenseFeature(Enum):
    UNLIMITED_RANGES = "unlimited_ranges"
    UNLIMITED_REPORTS = "unlimited_reports"
    PDF_EXPORT = "pdf_export"
    CSV_EXPORT = "csv_export"
    HACKRF_SUPPORT = "hackrf_support"
    API_ACCESS = "api_access"


@dataclass
class LicenseInfo:
    """Информация о лицензии"""
    license_type: LicenseType
    machine_id: str
    created_at: datetime
    expires_at: datetime
    max_ranges: int
    max_reports_per_day: int
    features: list[LicenseFeature]
    license_key: str = ""
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @property
    def is_trial(self) -> bool:
        return self.license_type == LicenseType.TRIAL
    
    @property
    def days_remaining(self) -> int:
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)
    
    def has_feature(self, feature: LicenseFeature) -> bool:
        return feature in self.features
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "license_type": self.license_type.value,
            "machine_id": self.machine_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "max_ranges": self.max_ranges,
            "max_reports_per_day": self.max_reports_per_day,
            "features": [f.value for f in self.features],
            "license_key": self.license_key,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LicenseInfo:
        return cls(
            license_type=LicenseType(data["license_type"]),
            machine_id=data["machine_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            max_ranges=data["max_ranges"],
            max_reports_per_day=data["max_reports_per_day"],
            features=[LicenseFeature(f) for f in data["features"]],
            license_key=data.get("license_key", ""),
        )


class LicenseManager:
    """Менеджер лицензий"""
    
    LICENSE_FILE = "license.json"
    USAGE_FILE = "usage.json"
    
    # Режим разработки - снимает все ограничения
    DEV_MODE = True
    
    # Параметры trial версии
    TRIAL_DAYS = 7
    TRIAL_MAX_RANGES = 1
    TRIAL_MAX_REPORTS = 1
    TRIAL_FEATURES = [
        LicenseFeature.PDF_EXPORT,
        LicenseFeature.CSV_EXPORT,
    ]
    
    # Параметры Pro версии
    PRO_FEATURES = [
        LicenseFeature.UNLIMITED_RANGES,
        LicenseFeature.UNLIMITED_REPORTS,
        LicenseFeature.PDF_EXPORT,
        LicenseFeature.CSV_EXPORT,
        LicenseFeature.HACKRF_SUPPORT,
    ]
    
    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = self._get_default_data_dir()
        
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._license: LicenseInfo | None = None
        self._daily_report_count = 0
        self._last_report_date: datetime | None = None
        
        self._load_license()
        self._load_usage()
    
    def _get_default_data_dir(self) -> Path:
        """Получить директорию данных по умолчанию"""
        if platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", "~"))
        else:
            base = Path("~/.config")
        
        return base.expanduser() / "rf-analyzer"
    
    def _get_machine_id(self) -> str:
        """Получить уникальный ID машины"""
        # Используем комбинацию характеристик системы
        info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        
        # Добавляем MAC-адрес если возможно
        try:
            mac = uuid.getnode()
            info += f"-{mac}"
        except Exception:
            pass
        
        return hashlib.sha256(info.encode()).hexdigest()[:32]
    
    def _load_license(self) -> None:
        """Загрузить лицензию из файла"""
        license_path = self.data_dir / self.LICENSE_FILE
        
        if license_path.exists():
            try:
                with open(license_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._license = LicenseInfo.from_dict(data)
                
                # Проверяем машину
                if self._license.machine_id != self._get_machine_id():
                    logger.warning("License machine ID mismatch")
                    self._license = None
                    
            except Exception as e:
                logger.error(f"Failed to load license: {e}")
                self._license = None
    
    def _save_license(self) -> None:
        """Сохранить лицензию в файл"""
        if not self._license:
            return
        
        license_path = self.data_dir / self.LICENSE_FILE
        
        with open(license_path, "w", encoding="utf-8") as f:
            json.dump(self._license.to_dict(), f, indent=2)
    
    def _load_usage(self) -> None:
        """Загрузить данные использования"""
        usage_path = self.data_dir / self.USAGE_FILE
        
        if usage_path.exists():
            try:
                with open(usage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self._daily_report_count = data.get("report_count", 0)
                last_date = data.get("last_date")
                if last_date:
                    self._last_report_date = datetime.fromisoformat(last_date)
                    
                    # Сброс счётчика на новый день
                    if self._last_report_date.date() != datetime.now().date():
                        self._daily_report_count = 0
                        self._last_report_date = None
                        
            except Exception as e:
                logger.error(f"Failed to load usage: {e}")
    
    def _save_usage(self) -> None:
        """Сохранить данные использования"""
        usage_path = self.data_dir / self.USAGE_FILE
        
        data = {
            "report_count": self._daily_report_count,
            "last_date": datetime.now().isoformat(),
        }
        
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def get_license(self) -> LicenseInfo | None:
        """Получить текущую лицензию"""
        return self._license
    
    def is_licensed(self) -> bool:
        """Проверить наличие действующей лицензии"""
        # Программа теперь бесплатная - всегда возвращаем True
        return True
    
    def start_trial(self) -> LicenseInfo:
        """Начать пробный период"""
        if self._license and not self._license.is_expired:
            raise ValueError("Active license already exists")
        
        machine_id = self._get_machine_id()
        now = datetime.now()
        
        self._license = LicenseInfo(
            license_type=LicenseType.TRIAL,
            machine_id=machine_id,
            created_at=now,
            expires_at=now + timedelta(days=self.TRIAL_DAYS),
            max_ranges=self.TRIAL_MAX_RANGES,
            max_reports_per_day=self.TRIAL_MAX_REPORTS,
            features=self.TRIAL_FEATURES.copy(),
        )
        
        self._save_license()
        logger.info(f"Trial started, expires: {self._license.expires_at}")
        
        return self._license
    
    def activate_license(self, license_key: str) -> LicenseInfo:
        """Активировать лицензию по ключу"""
        # В реальном продукте здесь будет проверка на сервере
        # Для MVP - простая валидация формата
        
        if not self._validate_license_key(license_key):
            raise ValueError("Invalid license key format")
        
        machine_id = self._get_machine_id()
        now = datetime.now()
        
        # Определяем тип лицензии по ключу
        if license_key.startswith("PRO-"):
            license_type = LicenseType.PRO
            expires = now + timedelta(days=365)
            features = self.PRO_FEATURES.copy()
            max_ranges = 100
            max_reports = 100
        elif license_key.startswith("ENT-"):
            license_type = LicenseType.ENTERPRISE
            expires = now + timedelta(days=365)
            features = self.PRO_FEATURES.copy()
            features.append(LicenseFeature.API_ACCESS)
            max_ranges = 1000
            max_reports = 1000
        else:
            raise ValueError("Unknown license type")
        
        self._license = LicenseInfo(
            license_type=license_type,
            machine_id=machine_id,
            created_at=now,
            expires_at=expires,
            max_ranges=max_ranges,
            max_reports_per_day=max_reports,
            features=features,
            license_key=license_key,
        )
        
        self._save_license()
        logger.info(f"License activated: {license_type.value}, expires: {expires}")
        
        return self._license
    
    def _validate_license_key(self, key: str) -> bool:
        """Базовая валидация формата ключа"""
        # Формат: TYPE-XXXX-XXXX-XXXX-XXXX
        parts = key.split("-")
        if len(parts) != 5:
            return False
        
        if parts[0] not in ("PRO", "ENT"):
            return False
        
        for part in parts[1:]:
            if len(part) != 4 or not part.isalnum():
                return False
        
        return True
    
    def can_add_range(self, current_count: int) -> bool:
        """Проверить возможность добавления диапазона"""
        # Программа бесплатная - без ограничений
        return True
    
    def can_generate_report(self) -> bool:
        """Проверить возможность генерации отчёта"""
        # Программа бесплатная - без ограничений
        return True
    
    def record_report_generated(self) -> None:
        """Записать факт генерации отчёта"""
        today = datetime.now()
        
        if self._last_report_date and self._last_report_date.date() != today.date():
            self._daily_report_count = 0
        
        self._daily_report_count += 1
        self._last_report_date = today
        self._save_usage()
    
    def get_status(self) -> dict[str, Any]:
        """Получить статус лицензии"""
        if not self._license:
            return {
                "status": "no_license",
                "message": "Лицензия не активирована. Запустите пробный период.",
            }
        
        if self._license.is_expired:
            return {
                "status": "expired",
                "message": f"Лицензия истекла {self._license.expires_at.strftime('%d.%m.%Y')}",
                "license_type": self._license.license_type.value,
            }
        
        return {
            "status": "active",
            "license_type": self._license.license_type.value,
            "days_remaining": self._license.days_remaining,
            "expires_at": self._license.expires_at.strftime("%d.%m.%Y"),
            "max_ranges": self._license.max_ranges,
            "reports_today": self._daily_report_count,
            "max_reports_per_day": self._license.max_reports_per_day,
            "features": [f.value for f in self._license.features],
        }
