"""
RF Event Analyzer - Event Storage (SQLite)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from rf_analyzer.core.config import EventType, RFEvent

logger = logging.getLogger(__name__)


class EventStorage:
    """SQLite хранилище RF-событий"""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TEXT NOT NULL,
        end_time TEXT,
        duration_ms REAL NOT NULL,
        range_name TEXT NOT NULL,
        center_freq REAL NOT NULL,
        bandwidth REAL NOT NULL,
        max_power_db REAL NOT NULL,
        avg_power_db REAL NOT NULL,
        event_type TEXT NOT NULL,
        comment TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
    CREATE INDEX IF NOT EXISTS idx_events_range_name ON events(range_name);
    CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
    
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Инициализация базы данных"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
        
        logger.info(f"Database initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Получить соединение с БД"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def save_event(self, event: RFEvent) -> int:
        """Сохранить событие, вернуть ID"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO events (
                        start_time, end_time, duration_ms, range_name,
                        center_freq, bandwidth, max_power_db, avg_power_db,
                        event_type, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.start_time.isoformat(),
                        event.end_time.isoformat() if event.end_time else None,
                        event.duration_ms,
                        event.range_name,
                        event.center_freq,
                        event.bandwidth,
                        event.max_power_db,
                        event.avg_power_db,
                        event.event_type.value,
                        event.comment,
                    )
                )
                conn.commit()
                event_id = cursor.lastrowid
                logger.debug(f"Event saved: ID={event_id}")
                return event_id
    
    def get_event(self, event_id: int) -> RFEvent | None:
        """Получить событие по ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            
            if row:
                return self._row_to_event(row)
            return None
    
    def get_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        range_name: str | None = None,
        event_type: EventType | None = None,
        limit: int = 1000,
        offset: int = 0
    ) -> list[RFEvent]:
        """Получить события с фильтрацией"""
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        
        if start_time:
            query += " AND start_time >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND start_time <= ?"
            params.append(end_time.isoformat())
        
        if range_name:
            query += " AND range_name = ?"
            params.append(range_name)
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        
        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_events_last_hours(self, hours: int) -> list[RFEvent]:
        """Получить события за последние N часов"""
        start_time = datetime.now() - timedelta(hours=hours)
        return self.get_events(start_time=start_time)
    
    def get_events_for_report(
        self,
        start_time: datetime,
        end_time: datetime,
        range_names: list[str] | None = None
    ) -> list[RFEvent]:
        """Получить события для отчёта"""
        query = """
            SELECT * FROM events 
            WHERE start_time >= ? AND start_time <= ?
        """
        params: list[Any] = [start_time.isoformat(), end_time.isoformat()]
        
        if range_names:
            placeholders = ",".join("?" * len(range_names))
            query += f" AND range_name IN ({placeholders})"
            params.extend(range_names)
        
        query += " ORDER BY start_time ASC"
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def get_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> dict[str, Any]:
        """Получить статистику событий"""
        where_clause = "WHERE 1=1"
        params: list[Any] = []
        
        if start_time:
            where_clause += " AND start_time >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            where_clause += " AND start_time <= ?"
            params.append(end_time.isoformat())
        
        with self._get_connection() as conn:
            # Общее количество
            total = conn.execute(
                f"SELECT COUNT(*) FROM events {where_clause}", params
            ).fetchone()[0]
            
            # По типам
            by_type = dict(conn.execute(
                f"""
                SELECT event_type, COUNT(*) 
                FROM events {where_clause}
                GROUP BY event_type
                """, params
            ).fetchall())
            
            # По диапазонам
            by_range = dict(conn.execute(
                f"""
                SELECT range_name, COUNT(*) 
                FROM events {where_clause}
                GROUP BY range_name
                """, params
            ).fetchall())
            
            # Средняя длительность
            avg_duration = conn.execute(
                f"SELECT AVG(duration_ms) FROM events {where_clause}", params
            ).fetchone()[0] or 0
            
            # Максимальный уровень
            max_power = conn.execute(
                f"SELECT MAX(max_power_db) FROM events {where_clause}", params
            ).fetchone()[0] or -100
        
        return {
            "total_events": total,
            "by_type": by_type,
            "by_range": by_range,
            "avg_duration_ms": avg_duration,
            "max_power_db": max_power,
        }
    
    def get_range_names(self) -> list[str]:
        """Получить список всех диапазонов с событиями"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT range_name FROM events ORDER BY range_name"
            ).fetchall()
            return [row[0] for row in rows]
    
    def count_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> int:
        """Подсчитать количество событий"""
        query = "SELECT COUNT(*) FROM events WHERE 1=1"
        params: list[Any] = []
        
        if start_time:
            query += " AND start_time >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND start_time <= ?"
            params.append(end_time.isoformat())
        
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]
    
    def delete_old_events(self, days: int) -> int:
        """Удалить события старше N дней"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM events WHERE start_time < ?",
                    (cutoff.isoformat(),)
                )
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Deleted {deleted} old events")
                return deleted
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Сохранить метаданные"""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO metadata (key, value)
                    VALUES (?, ?)
                    """,
                    (key, json.dumps(value))
                )
                conn.commit()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Получить метаданные"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
            
            if row:
                return json.loads(row[0])
            return default
    
    def _row_to_event(self, row: sqlite3.Row) -> RFEvent:
        """Преобразовать строку БД в объект события"""
        return RFEvent(
            id=row["id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_ms=row["duration_ms"],
            range_name=row["range_name"],
            center_freq=row["center_freq"],
            bandwidth=row["bandwidth"],
            max_power_db=row["max_power_db"],
            avg_power_db=row["avg_power_db"],
            event_type=EventType(row["event_type"]),
            comment=row["comment"] or "",
        )
    
    def close(self) -> None:
        """Закрыть хранилище"""
        pass  # SQLite закрывает соединения автоматически
