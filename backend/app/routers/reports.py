"""
SkyShield Reports API
Генерация PDF и HTML отчетов из данных мониторинга
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta
from pathlib import Path
import io
import tempfile

from app.database import get_db
from app.models.telemetry import Telemetry

# Для генерации PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False


def _register_pdf_font() -> str:
    """Регистрирует шрифт с поддержкой кириллицы для ReportLab.

    Возвращает имя шрифта для использования в ParagraphStyle/TableStyle.
    """
    if not HAVE_REPORTLAB:
        return "Helvetica"

    # Стандартные Helvetica/Times не умеют кириллицу — получаются квадраты.
    # В образе устанавливаем fonts-dejavu-core, поэтому ожидаем DejaVuSans.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", path))
                return "DejaVuSans"
            except Exception:
                # если регистрация не удалась — используем дефолт
                break
    return "Helvetica"

# Для графиков
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    HAVE_MATPLOTLIB = True
except ImportError:
    HAVE_MATPLOTLIB = False

router = APIRouter(prefix="/reports", tags=["reports"])

PDF_FONT_NAME = _register_pdf_font()


@router.get("/", response_class=HTMLResponse)
async def reports_dashboard():
    """Главная страница отчетов с формой"""
    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SkyShield — Генерация отчетов</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1e1e2e 0%, #2d2d3d 100%);
                color: #e4e4e7;
                min-height: 100vh;
                padding: 40px 20px;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: #2d2d3d;
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            h1 {
                color: #60a5fa;
                font-size: 32px;
                margin-bottom: 10px;
                text-align: center;
            }
            .subtitle {
                text-align: center;
                color: #a1a1aa;
                margin-bottom: 40px;
                font-size: 14px;
            }
            .form-group {
                margin-bottom: 24px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #e4e4e7;
                font-weight: 500;
            }
            input[type="datetime-local"],
            input[type="text"] {
                width: 100%;
                padding: 12px 16px;
                background: #1e1e2e;
                border: 2px solid #4d4d5f;
                border-radius: 8px;
                color: #e4e4e7;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input:focus {
                outline: none;
                border-color: #60a5fa;
            }
            .button-group {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                margin-top: 32px;
            }
            button {
                padding: 14px 24px;
                font-size: 16px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .btn-pdf {
                background: linear-gradient(135deg, #f87171 0%, #dc2626 100%);
                color: white;
            }
            .btn-pdf:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(248, 113, 113, 0.4);
            }
            .btn-html {
                background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
                color: white;
            }
            .btn-html:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(96, 165, 250, 0.4);
            }
            .info-box {
                background: #3d3d4f;
                border-left: 4px solid #60a5fa;
                padding: 16px;
                border-radius: 8px;
                margin-top: 24px;
            }
            .info-box p {
                color: #a1a1aa;
                font-size: 14px;
                line-height: 1.6;
            }
            .quick-links {
                display: flex;
                gap: 12px;
                margin-top: 16px;
            }
            .quick-link {
                padding: 8px 16px;
                background: #4d4d5f;
                border-radius: 6px;
                color: #60a5fa;
                text-decoration: none;
                font-size: 13px;
                transition: background 0.3s;
            }
            .quick-link:hover {
                background: #5d5d6f;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ SkyShield</h1>
            <div class="subtitle">Система генерации отчетов мониторинга</div>
            
            <form id="reportForm">
                <div class="form-group">
                    <label for="startDate">Начало периода:</label>
                    <input type="datetime-local" id="startDate" required>
                </div>
                
                <div class="form-group">
                    <label for="endDate">Конец периода:</label>
                    <input type="datetime-local" id="endDate" required>
                </div>
                
                <div class="form-group">
                    <label for="deviceId">ID устройства (опционально):</label>
                    <input type="text" id="deviceId" placeholder="DRONE-HUNTER-01">
                </div>
                
                <div class="button-group">
                    <button type="button" class="btn-pdf" onclick="downloadPDF()">
                        📄 Скачать PDF
                    </button>
                    <button type="button" class="btn-html" onclick="openHTML()">
                        🌐 Открыть HTML
                    </button>
                </div>
            </form>
            
            <div class="info-box">
                <p><strong>Быстрые отчеты:</strong></p>
                <div class="quick-links">
                    <a href="#" class="quick-link" onclick="setLastHour()">Последний час</a>
                    <a href="#" class="quick-link" onclick="setLast24Hours()">Последние 24 часа</a>
                    <a href="#" class="quick-link" onclick="setToday()">Сегодня</a>
                </div>
            </div>
        </div>
        
        <script>
            // Установить дефолтные значения (последние 24 часа)
            window.onload = function() {
                setLast24Hours();
            };
            
            function setLastHour() {
                const now = new Date();
                const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);
                document.getElementById('endDate').value = formatDateTime(now);
                document.getElementById('startDate').value = formatDateTime(hourAgo);
            }
            
            function setLast24Hours() {
                const now = new Date();
                const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                document.getElementById('endDate').value = formatDateTime(now);
                document.getElementById('startDate').value = formatDateTime(dayAgo);
            }
            
            function setToday() {
                const now = new Date();
                const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                document.getElementById('endDate').value = formatDateTime(now);
                document.getElementById('startDate').value = formatDateTime(startOfDay);
            }
            
            function formatDateTime(date) {
                const pad = (n) => n.toString().padStart(2, '0');
                return date.getFullYear() + '-' +
                       pad(date.getMonth() + 1) + '-' +
                       pad(date.getDate()) + 'T' +
                       pad(date.getHours()) + ':' +
                       pad(date.getMinutes());
            }
            
            function getParams() {
                const startDate = document.getElementById('startDate').value;
                const endDate = document.getElementById('endDate').value;
                const deviceId = document.getElementById('deviceId').value;
                
                if (!startDate || !endDate) {
                    alert('Пожалуйста, укажите период');
                    return null;
                }
                
                let params = `start_date=${encodeURIComponent(startDate + ':00')}&end_date=${encodeURIComponent(endDate + ':00')}`;
                if (deviceId) {
                    params += `&device_id=${encodeURIComponent(deviceId)}`;
                }
                return params;
            }
            
            function downloadPDF() {
                const params = getParams();
                if (params) {
                    window.location.href = `/api/v1/reports/pdf?${params}`;
                }
            }
            
            function openHTML() {
                const params = getParams();
                if (params) {
                    window.open(`/api/v1/reports/html?${params}`, '_blank');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


async def get_telemetry_data(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    device_id: str = None
):
    """Получить данные телеметрии за период"""
    query = select(Telemetry).where(
        and_(
            Telemetry.timestamp >= start_time,
            Telemetry.timestamp <= end_time
        )
    )
    
    if device_id:
        query = query.where(Telemetry.device_id == device_id)
    
    query = query.order_by(Telemetry.timestamp)
    result = await db.execute(query)
    return result.scalars().all()


async def get_statistics(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    device_id: str = None
):
    """Получить статистику за период"""
    query = select(Telemetry).where(
        and_(
            Telemetry.timestamp >= start_time,
            Telemetry.timestamp <= end_time
        )
    )
    
    if device_id:
        query = query.where(Telemetry.device_id == device_id)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    if not records:
        return {
            "total_records": 0,
            "avg_signal_level": 0,
            "max_signal_level": 0,
            "min_signal_level": 0,
            "critical_events": 0,
            "warning_events": 0
        }
    
    signal_levels = [r.velocity_rms_mm_s for r in records]
    
    return {
        "total_records": len(records),
        "avg_signal_level": sum(signal_levels) / len(signal_levels),
        "max_signal_level": max(signal_levels),
        "min_signal_level": min(signal_levels),
        "critical_events": sum(1 for r in records if r.status == "CRITICAL"),
        "warning_events": sum(1 for r in records if r.status == "WARNING")
    }


async def get_recent_events(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    device_id: str | None = None,
    limit: int = 20,
):
    """Получить последние WARNING/CRITICAL события за период."""
    limit = max(1, min(int(limit), 500))

    query = select(Telemetry).where(
        and_(
            Telemetry.timestamp >= start_time,
            Telemetry.timestamp <= end_time,
            Telemetry.status.in_(["WARNING", "CRITICAL"]),
        )
    )

    if device_id:
        query = query.where(Telemetry.device_id == device_id)

    query = query.order_by(desc(Telemetry.timestamp)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


def _normalize_freq_to_hz(value: float | None) -> float | None:
    """Нормализовать частоту к Гц.

    Исторически поле `dominant_freq_hz` могло приходить как МГц (433/868/915/1200).
    Чтобы отчеты были читаемыми, распознаем такие значения и переводим в Гц.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None

    # Если значение маленькое — считаем, что это МГц.
    # (433, 868, 915, 1200 и т.п.)
    if 1.0 < v < 20_000.0:
        return v * 1e6
    return v


def _fmt_freq(value: float | None) -> str:
    hz = _normalize_freq_to_hz(value)
    if hz is None:
        return "—"
    if hz >= 1_000_000_000:
        return f"{hz/1e9:.3f} ГГц"
    if hz >= 1_000_000:
        return f"{hz/1e6:.3f} МГц"
    return f"{hz:.0f} Гц"


def _status_severity(status: str) -> int:
    # Больше = хуже
    return 2 if status == "CRITICAL" else 1 if status == "WARNING" else 0


def build_incidents(
    events: list,
    *,
    gap_seconds: float = 2.0,
):
    """Склеить измерения WARNING/CRITICAL в инциденты.

    Инцидент завершается, если:
    - меняется `device_id`
    - разрыв по времени больше `gap_seconds`
    - статус перестает быть WARNING/CRITICAL
    """
    if not events:
        return []

    gap_seconds = max(0.1, float(gap_seconds))

    # Группируем по устройству, чтобы события разных устройств не смешивались.
    by_device: dict[str, list] = {}
    for ev in events:
        by_device.setdefault(ev.device_id, []).append(ev)

    incidents = []
    for dev, dev_events in by_device.items():
        # events приходят DESC по времени, приводим к ASC
        dev_events = sorted(dev_events, key=lambda r: r.timestamp)

        current = None
        for ev in dev_events:
            if ev.status not in ("WARNING", "CRITICAL"):
                continue

            if current is None:
                current = {
                    "device_id": dev,
                    "start": ev.timestamp,
                    "end": ev.timestamp,
                    "max_level": float(ev.velocity_rms_mm_s),
                    "max_status": ev.status,
                    "max_freq": ev.dominant_freq_hz,
                    "points": 1,
                }
                continue

            gap = (ev.timestamp - current["end"]).total_seconds()
            if gap > gap_seconds:
                incidents.append(current)
                current = {
                    "device_id": dev,
                    "start": ev.timestamp,
                    "end": ev.timestamp,
                    "max_level": float(ev.velocity_rms_mm_s),
                    "max_status": ev.status,
                    "max_freq": ev.dominant_freq_hz,
                    "points": 1,
                }
                continue

            current["end"] = ev.timestamp
            current["points"] += 1
            if float(ev.velocity_rms_mm_s) >= current["max_level"]:
                current["max_level"] = float(ev.velocity_rms_mm_s)
                current["max_freq"] = ev.dominant_freq_hz
            if _status_severity(ev.status) > _status_severity(current["max_status"]):
                current["max_status"] = ev.status

        if current is not None:
            incidents.append(current)

    # Самые последние сверху
    incidents.sort(key=lambda x: x["end"], reverse=True)
    return incidents


def create_signal_plot(records) -> bytes | None:
    """Создать PNG-график уровня сигнала и вернуть байты.

    Важно: в ReportLab изображения читаются лениво во время doc.build(),
    поэтому используем in-memory PNG (BytesIO) вместо временных файлов.
    """
    if not HAVE_MATPLOTLIB:
        return None

    timestamps = [r.timestamp for r in records]
    signal_levels = [r.velocity_rms_mm_s for r in records]

    fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1e1e2e')
    ax.set_facecolor('#2d2d3d')

    ax.plot(timestamps, signal_levels, color='#60a5fa', linewidth=2)
    ax.fill_between(timestamps, signal_levels, alpha=0.3, color='#60a5fa')

    ax.axhline(y=50, color='#fbbf24', linestyle='--', alpha=0.5, label='Warning (50%)')
    ax.axhline(y=80, color='#f87171', linestyle='--', alpha=0.5, label='Critical (80%)')

    ax.set_xlabel('Время', color='#e4e4e7', fontsize=12)
    ax.set_ylabel('Уровень сигнала (%)', color='#e4e4e7', fontsize=12)
    ax.set_title('История уровня RF сигнала', color='#e4e4e7', fontsize=14, fontweight='bold')

    ax.tick_params(colors='#a1a1aa')
    ax.spines['bottom'].set_color('#4d4d5f')
    ax.spines['top'].set_color('#4d4d5f')
    ax.spines['left'].set_color('#4d4d5f')
    ax.spines['right'].set_color('#4d4d5f')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.xticks(rotation=45)

    ax.legend(loc='upper right', facecolor='#2d2d3d', edgecolor='#4d4d5f', labelcolor='#e4e4e7')
    ax.grid(True, alpha=0.1, color='#4d4d5f')

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor='#1e1e2e')
    plt.close(fig)
    return buf.getvalue()


@router.get("/pdf")
async def generate_pdf_report(
    start_date: datetime = Query(..., description="Начало периода"),
    end_date: datetime = Query(..., description="Конец периода"),
    device_id: str = Query(None, description="ID устройства"),
    events_limit: int = Query(20, ge=1, le=500, description="Сколько последних событий WARNING/CRITICAL включить"),
    incidents_limit: int = Query(10, ge=1, le=200, description="Сколько последних инцидентов включить"),
    incidents_gap_s: float = Query(2.0, ge=0.1, le=60.0, description="Максимальный разрыв (сек) между точками для склейки инцидента"),
    db: AsyncSession = Depends(get_db)
):
    """Сгенерировать PDF отчет за период"""
    
    if not HAVE_REPORTLAB:
        # Вернем HTML-заглушку вместо ошибки
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial; background: #1e1e2e; color: #e4e4e7; padding: 40px; text-align: center; }}
                .error {{ background: #dc2626; padding: 20px; border-radius: 8px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>❌ PDF генерация недоступна</h2>
                <p>Необходимо установить зависимости:</p>
                <code>pip install reportlab</code>
                <p style="margin-top: 20px;">
                    <a href="/api/v1/reports/html?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}" 
                       style="color: #60a5fa;">Открыть HTML версию отчета →</a>
                </p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    
    # Получить данные
    records = await get_telemetry_data(db, start_date, end_date, device_id)
    stats = await get_statistics(db, start_date, end_date, device_id)
    # Чтобы корректно склеить инциденты, берем больше точек, чем выводим в RAW-таблице.
    points_limit = max(events_limit, min(5000, incidents_limit * 500))
    events_points = await get_recent_events(db, start_date, end_date, device_id, points_limit)
    events = events_points[:events_limit]
    incidents = build_incidents(events_points, gap_seconds=incidents_gap_s)[:incidents_limit]
    
    if not records:
        raise HTTPException(status_code=404, detail="Нет данных за указанный период")
    
    # Создать временный файл
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp:
        pdf_path = Path(tmp.name)
    
    # Создать PDF
    # Чуть уменьшаем поля, чтобы таблицы уверенно помещались на A4
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    story = []
    styles = getSampleStyleSheet()

    normal_style = ParagraphStyle(
        'SkyShieldNormal',
        parent=styles['Normal'],
        fontName=PDF_FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#111827'),
    )

    table_cell_style = ParagraphStyle(
        'SkyShieldTableCell',
        parent=styles['Normal'],
        fontName=PDF_FONT_NAME,
        fontSize=8,
        leading=9,
        textColor=colors.HexColor('#111827'),
    )

    table_header_style = ParagraphStyle(
        'SkyShieldTableHeader',
        parent=styles['Normal'],
        fontName=PDF_FONT_NAME,
        fontSize=8,
        leading=9,
        textColor=colors.whitesmoke,
    )

    def _p(text: str, header: bool = False):
        return Paragraph(text, table_header_style if header else table_cell_style)
    
    # Заголовок
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        fontName=PDF_FONT_NAME,
        textColor=colors.HexColor('#60a5fa'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    story.append(Paragraph("SkyShield — Отчет мониторинга", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Информация о периоде
    story.append(Paragraph(f"<b>Период:</b> {start_date.strftime('%Y-%m-%d %H:%M')} — {end_date.strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Paragraph(f"<b>Устройство:</b> {device_id or 'Все устройства'}", normal_style))
    story.append(Paragraph(f"<b>Дата генерации:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Spacer(1, 1*cm))
    
    # Таблица статистики
    h2_style = ParagraphStyle(
        'SkyShieldH2',
        parent=styles['Heading2'],
        fontName=PDF_FONT_NAME,
        textColor=colors.HexColor('#111827'),
    )
    story.append(Paragraph("<b>Статистика</b>", h2_style))
    stat_data = [
        [_p('Параметр', header=True), _p('Значение', header=True)],
        [_p('Всего записей'), _p(f"{stats['total_records']}")],
        [_p('Средний уровень сигнала'), _p(f"{stats['avg_signal_level']:.1f}%")],
        [_p('Максимальный уровень'), _p(f"{stats['max_signal_level']:.1f}%")],
        [_p('Минимальный уровень'), _p(f"{stats['min_signal_level']:.1f}%")],
        [_p('Критических событий'), _p(f"{stats['critical_events']}")],
        [_p('Предупреждений'), _p(f"{stats['warning_events']}")]
    ]
    
    stat_table = Table(stat_data, colWidths=[10*cm, 6*cm])
    stat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#60a5fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), PDF_FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4d4d5f'))
    ]))
    
    story.append(stat_table)
    story.append(Spacer(1, 1*cm))

    # Последние инциденты (склейка)
    if incidents:
        story.append(Paragraph(f"<b>Последние инциденты (TOP {len(incidents)})</b>", h2_style))

        inc_table_data = [[
            _p('Начало', header=True),
            _p('Окончание', header=True),
            _p('Длительность', header=True),
            _p('Устройство', header=True),
            _p('Класс', header=True),
            _p('Пик', header=True),
            _p('Частота', header=True),
            _p('Точек', header=True),
        ]]
        for inc in incidents:
            duration_s = max(0.0, (inc["end"] - inc["start"]).total_seconds())
            if duration_s >= 60:
                duration_str = f"{duration_s/60:.1f} мин"
            else:
                duration_str = f"{duration_s:.1f} с"

            inc_table_data.append([
                _p(inc["start"].strftime('%Y-%m-%d %H:%M:%S')),
                _p(inc["end"].strftime('%Y-%m-%d %H:%M:%S')),
                _p(duration_str),
                _p(inc["device_id"]),
                _p(inc["max_status"]),
                _p(f"{inc['max_level']:.1f}%"),
                _p(_fmt_freq(inc.get("max_freq"))),
                _p(str(inc["points"])),
            ])

        inc_table = Table(
            inc_table_data,
            # Подгоняем под ширину листа, чтобы колонки не наезжали друг на друга
            colWidths=[
                3.0*cm,  # начало
                3.0*cm,  # окончание
                1.6*cm,  # длительность
                3.4*cm,  # устройство
                1.6*cm,  # класс
                1.4*cm,  # пик
                2.4*cm,  # частота
                1.2*cm,  # точек
            ],
            repeatRows=1,
        )

        ts = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, -1), PDF_FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEADING', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4d4d5f')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
        ]

        for idx, inc in enumerate(incidents, start=1):
            if inc["max_status"] == "CRITICAL":
                ts.append(('TEXTCOLOR', (0, idx), (-1, idx), colors.HexColor('#b91c1c')))
                ts.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fee2e2')))
            elif inc["max_status"] == "WARNING":
                ts.append(('TEXTCOLOR', (0, idx), (-1, idx), colors.HexColor('#92400e')))
                ts.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fef3c7')))

        inc_table.setStyle(TableStyle(ts))
        story.append(inc_table)
        story.append(Spacer(1, 1*cm))

    # Последние события (RAW)
    if events:
        story.append(Paragraph(f"<b>Последние события (TOP {len(events)})</b>", h2_style))

        events_table_data = [[
            _p('Время', header=True),
            _p('Устройство', header=True),
            _p('Статус', header=True),
            _p('Уровень', header=True),
            _p('Частота', header=True),
        ]]
        for ev in events:
            events_table_data.append([
                _p(ev.timestamp.strftime('%Y-%m-%d %H:%M:%S')),
                _p(ev.device_id),
                _p(ev.status),
                _p(f"{ev.velocity_rms_mm_s:.1f}%"),
                _p(_fmt_freq(ev.dominant_freq_hz)),
            ])

        events_table = Table(
            events_table_data,
            colWidths=[4.0*cm, 4.2*cm, 2.0*cm, 2.0*cm, 3.0*cm],
            repeatRows=1,
        )
        ts = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, -1), PDF_FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEADING', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4d4d5f')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
        ]

        # Подсветка статусов
        for idx, ev in enumerate(events, start=1):
            if ev.status == "CRITICAL":
                ts.append(('TEXTCOLOR', (0, idx), (-1, idx), colors.HexColor('#b91c1c')))
                ts.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fee2e2')))
            elif ev.status == "WARNING":
                ts.append(('TEXTCOLOR', (0, idx), (-1, idx), colors.HexColor('#92400e')))
                ts.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fef3c7')))

        events_table.setStyle(TableStyle(ts))
        story.append(events_table)
        story.append(Spacer(1, 1*cm))
    
    # График (matplotlib опционален)
    if HAVE_MATPLOTLIB and len(records) > 1:
        plot_bytes = create_signal_plot(records)
        if plot_bytes:
            story.append(Paragraph("<b>График уровня сигнала</b>", h2_style))
            img = Image(io.BytesIO(plot_bytes), width=16*cm, height=8*cm)
            story.append(img)
    
    # Построить PDF
    doc.build(story)
    
    def _cleanup_pdf(path_str: str) -> None:
        try:
            Path(path_str).unlink(missing_ok=True)
        except Exception:
            pass

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"skyshield_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
        background=BackgroundTask(_cleanup_pdf, str(pdf_path)),
    )


@router.get("/html", response_class=HTMLResponse)
async def generate_html_report(
    start_date: datetime = Query(..., description="Начало периода"),
    end_date: datetime = Query(..., description="Конец периода"),
    device_id: str = Query(None, description="ID устройства"),
    db: AsyncSession = Depends(get_db)
):
    """Сгенерировать HTML отчет за период"""
    
    records = await get_telemetry_data(db, start_date, end_date, device_id)
    stats = await get_statistics(db, start_date, end_date, device_id)
    
    if not records:
        return "<html><body><h1>Нет данных за указанный период</h1></body></html>"
    
    # Простой HTML отчет
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>SkyShield — Отчет</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #1e1e2e; color: #e4e4e7; padding: 20px; }}
            h1 {{ color: #60a5fa; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #60a5fa; color: white; padding: 10px; }}
            td {{ background: #2d2d3d; padding: 10px; border: 1px solid #4d4d5f; }}
            .critical {{ color: #f87171; font-weight: bold; }}
            .warning {{ color: #fbbf24; }}
        </style>
    </head>
    <body>
        <h1>SkyShield — Отчет мониторинга</h1>
        <p><b>Период:</b> {start_date.strftime('%Y-%m-%d %H:%M')} — {end_date.strftime('%Y-%m-%d %H:%M')}</p>
        <p><b>Устройство:</b> {device_id or 'Все устройства'}</p>
        
        <h2>Статистика</h2>
        <table>
            <tr><th>Параметр</th><th>Значение</th></tr>
            <tr><td>Всего записей</td><td>{stats['total_records']}</td></tr>
            <tr><td>Средний уровень сигнала</td><td>{stats['avg_signal_level']:.1f}%</td></tr>
            <tr><td>Максимальный уровень</td><td>{stats['max_signal_level']:.1f}%</td></tr>
            <tr><td>Критических событий</td><td class="critical">{stats['critical_events']}</td></tr>
            <tr><td>Предупреждений</td><td class="warning">{stats['warning_events']}</td></tr>
        </table>
        
        <h2>Последние события</h2>
        <table>
            <tr><th>Время</th><th>Уровень сигнала</th><th>Статус</th></tr>
    """
    
    for record in records[-50:]:  # Последние 50 записей
        status_class = 'critical' if record.status == 'CRITICAL' else ('warning' if record.status == 'WARNING' else '')
        html += f"""
            <tr>
                <td>{record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                <td>{record.velocity_rms_mm_s:.1f}%</td>
                <td class="{status_class}">{record.status}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


@router.get("/summary")
async def get_report_summary(
    start_date: datetime = Query(..., description="Начало периода"),
    end_date: datetime = Query(..., description="Конец периода"),
    device_id: str = Query(None, description="ID устройства"),
    db: AsyncSession = Depends(get_db)
):
    """Получить краткую сводку за период (JSON)"""
    
    stats = await get_statistics(db, start_date, end_date, device_id)
    
    return {
        "period": {
            "start": start_date,
            "end": end_date
        },
        "device_id": device_id,
        "statistics": stats
    }
