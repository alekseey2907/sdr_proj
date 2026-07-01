from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkyShield — Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-main: #e6edf3;
            --text-sub: #8b949e;
            --danger: #f85149;
            --success: #2ea043;
            --warning: #d29922;
            --chart-grid: #30363d;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Segoe UI', sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 0 10px;
        }
        h1 { margin: 0; font-size: 24px; display: flex; align-items: center; gap: 10px; }
        .status-badge {
            background: var(--card-bg);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            border: 1px solid #30363d;
        }
        .grid-container {
            display: grid;
            grid-template-columns: 340px 1fr;
            grid-template-rows: 240px 400px 320px 320px;
            gap: 20px;
            flex-grow: 1;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow: hidden; /* Чтобы контент не вылезал */
        }
        .card-title {
            color: var(--text-sub);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 15px;
        }
        /* GAUGE */
        .gauge-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            position: relative;
        }
        .gauge-value {
            font-size: 64px;
            font-weight: bold;
            color: var(--success);
            text-shadow: 0 0 20px rgba(46, 160, 67, 0.4);
        }
        .gauge-label {
            font-size: 14px;
            color: var(--text-sub);
            margin-top: -10px;
        }
        
        /* SPECTRUM */
        .bars-container {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 100%;
            gap: 5px;
            padding-top: 20px;
        }
        .bar-group {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }
        .bar-wrapper {
            width: 100%;
            height: 120px;
            background: #21262d;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: flex-end;
        }
        .bar {
            width: 100%;
            background: var(--success);
            transition: height 0.3s ease;
            box-shadow: 0 0 10px rgba(46, 160, 67, 0.3);
        }
        .bar-val {
            margin-bottom: 5px;
            font-size: 14px;
            font-weight: bold;
        }
        .bar-label {
            margin-top: 8px;
            font-size: 11px;
            color: var(--text-sub);
            text-align: center;
        }

        /* HISTORY */
        .history-container {
            grid-column: 1 / -1;
            /* Height controlled by grid */
            padding-bottom: 20px; /* Extra space for x-axis labels */
        }
        .narrowband-container {
            grid-column: 1 / -1;
            padding-bottom: 20px;
        }
        .narrowband-meta {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 10px;
            color: var(--text-sub);
            font-size: 13px;
        }
        .peak-pill {
            border: 1px solid #30363d;
            border-radius: 999px;
            padding: 4px 10px;
            font-weight: 600;
            color: #8b949e;
            background: #11161d;
        }
        .peak-pill.active {
            color: #ffd866;
            border-color: rgba(255, 216, 102, 0.45);
            box-shadow: 0 0 18px rgba(255, 216, 102, 0.15);
        }
        canvas { 
            width: 100% !important; 
            height: calc(100% - 20px) !important; /* Leave space for labels */
        }

        /* ALERT MODE */
        body.alert-mode .gauge-value { color: var(--danger); text-shadow: 0 0 30px red; }
        body.alert-mode .bar { background: var(--danger); box-shadow: 0 0 15px red; }

        /* WARNING MODE */
        body.warning-mode .gauge-value { color: var(--warning); text-shadow: 0 0 20px orange; }
        body.warning-mode .bar { background: var(--warning); box-shadow: 0 0 10px orange; }
    </style>
</head>
<body>
    <header>
        <h1>🛡️ SkyShield <span style="font-size: 14px; color: #8b949e; font-weight: normal;">v2.0 (Embedded)</span></h1>
        <div style="display:flex; align-items:center; gap:12px;">
            <a href="/settings" style="color:#79c0ff; text-decoration:none; font-size:14px;">Settings</a>
            <div class="status-badge" id="connStatus">CONNECTING...</div>
        </div>
    </header>

    <div class="grid-container">
        <!-- THREAT LEVEL -->
        <div class="card">
            <div class="card-title">Threat Level / Уровень Угрозы</div>
            <div class="gauge-container">
                <!-- Simple CSS Gauge Arc could be here, using text for now -->
                <div class="gauge-value" id="threatValue">0.0</div>
                <div class="gauge-label">SAFE</div>
            </div>
        </div>

        <!-- SPECTRUM -->
        <div class="card">
            <div class="card-title">Spectrum Analysis</div>
            <div class="bars-container" id="spectrumBars">
                <!-- Bars generated by JS -->
            </div>
        </div>

        <!-- HISTORY -->
        <div class="card history-container">
            <div class="card-title">Signal Signature History</div>
            <canvas id="historyChart"></canvas>
        </div>

        <!-- 868-870 LIVE SPECTRUM -->
        <div class="card narrowband-container">
            <div class="card-title">Live Spectrum 868-870 MHz / Power in dBm</div>
            <div class="narrowband-meta">
                <div id="live868Meta">Noise floor: -- dBm | Peak: -- dBm | Delta: -- dB</div>
                <div class="peak-pill" id="live868PeakFlag">NO PEAK</div>
            </div>
            <canvas id="live868Chart"></canvas>
        </div>

        <!-- 1279-1281 LIVE SPECTRUM -->
        <div class="card narrowband-container">
            <div class="card-title">Live Spectrum 1279-1281 MHz / Power in dBm</div>
            <div class="narrowband-meta">
                <div id="live1280Meta">Noise floor: -- dBm | Peak: -- dBm | Delta: -- dB</div>
                <div class="peak-pill" id="live1280PeakFlag">NO PEAK</div>
            </div>
            <canvas id="live1280Chart"></canvas>
        </div>
    </div>

    <script>
        // CONFIG
        const DEVICE_ID = new URLSearchParams(window.location.search).get('device_id') || "DRONE-HUNTER-01";
        const API_URL = `/api/v1/telemetry/${DEVICE_ID}/latest`;
        const MAX_CONSECUTIVE_ERRORS = 3;
        const TELEMETRY_STALE_MS = 15000;
        const LABELS = ["868 MHz", "1280 MHz"];
        let consecutiveErrors = 0;
        let lastTelemetryAtMs = null;

        // Normalize timestamps coming from backend.
        // If timezone is missing, treat it as UTC by appending 'Z'.
        // IMPORTANT: do NOT use ts.includes('-') because ISO date part contains '-'.
        function normalizeTimestampString(ts) {
            if (!ts) return null;
            // Has explicit timezone suffix?
            // Examples: ...Z, ...+03:00, ...-05:00
            if (/(Z|[+-]\\d\\d:\\d\\d)$/.test(ts)) return ts;
            return ts + 'Z';
        }

        function toTimeLabel(ts) {
            const normalized = normalizeTimestampString(ts);
            const d = normalized ? new Date(normalized) : new Date();
            return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }

        function setConnectionStatus(text, color) {
            document.getElementById('connStatus').innerText = text;
            document.getElementById('connStatus').style.color = color;
        }

        function updateConnectionBadge() {
            if (lastTelemetryAtMs === null) {
                setConnectionStatus('CONNECTING...', '#8b949e');
                return;
            }

            const telemetryAgeMs = Date.now() - lastTelemetryAtMs;
            if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS || telemetryAgeMs > TELEMETRY_STALE_MS) {
                setConnectionStatus('OFFLINE', '#f85149');
                return;
            }

            setConnectionStatus('ONLINE', '#2ea043');
        }
        
        // INIT CHARTS
        const ctx = document.getElementById('historyChart').getContext('2d');
        const historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(50).fill(''),
                datasets: [{
                    label: 'RF Level',
                    data: Array(50).fill(0),
                    borderColor: '#2ea043',
                    backgroundColor: 'rgba(46, 160, 67, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    y: { 
                        min: 0, 
                        max: 100, 
                        grid: { color: '#30363d' },
                        ticks: { color: '#8b949e', font: { size: 10 } }
                    },
                    x: { 
                        grid: { color: '#30363d' },
                        ticks: { 
                            color: '#8b949e', 
                            font: { size: 9 },
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 12
                        }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });

        function colorWithAlpha(hexColor, alpha) {
            const normalized = hexColor.replace('#', '');
            const r = parseInt(normalized.slice(0, 2), 16);
            const g = parseInt(normalized.slice(2, 4), 16);
            const b = parseInt(normalized.slice(4, 6), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }

        function createNarrowbandChart(canvasId, label, color) {
            const ctx = document.getElementById(canvasId).getContext('2d');
            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label,
                        data: [],
                        borderColor: color,
                        backgroundColor: colorWithAlpha(color, 0.16),
                        borderWidth: 2,
                        tension: 0.15,
                        fill: true,
                        pointRadius: 0
                    }, {
                        label: 'Peak',
                        data: [],
                        showLine: false,
                        pointRadius: 5,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#ffd866',
                        pointBorderColor: '#11161d',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        y: {
                            grid: { color: '#30363d' },
                            ticks: { color: '#8b949e', font: { size: 10 } },
                            min: -110,
                            max: -30,
                            title: { display: true, text: 'dBm', color: '#8b949e' }
                        },
                        x: {
                            grid: { color: '#30363d' },
                            ticks: {
                                color: '#8b949e',
                                font: { size: 9 },
                                autoSkip: true,
                                maxTicksLimit: 10,
                                maxRotation: 0,
                                callback: function(value) {
                                    const labelValue = this.getLabelForValue(value);
                                    return Number(labelValue).toFixed(2);
                                }
                            },
                            title: { display: true, text: 'MHz', color: '#8b949e' }
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        const live868Chart = createNarrowbandChart('live868Chart', '868-870 MHz', '#3fb950');
        const live1280Chart = createNarrowbandChart('live1280Chart', '1279-1281 MHz', '#d29922');

        // GENERATE BARS HTML
        const barsContainer = document.getElementById('spectrumBars');
        LABELS.forEach((label, idx) => {
            const div = document.createElement('div');
            div.className = 'bar-group';
            div.innerHTML = `
                <div class="bar-val" id="val-${idx}">0.0</div>
                <div class="bar-wrapper"><div class="bar" id="bar-${idx}" style="height: 0%"></div></div>
                <div class="bar-label">${label}</div>
            `;
            barsContainer.appendChild(div);
        });

        // LOAD HISTORY FROM DATABASE
        async function loadHistory() {
            try {
                const res = await fetch(`/api/v1/telemetry/${DEVICE_ID}?limit=200`);
                if (!res.ok) return;
                const history = await res.json();
                
                // Populate chart with historical data
                const chartData = historyChart.data.datasets[0].data;
                const chartLabels = historyChart.data.labels;
                
                // Clear existing
                chartData.length = 0;
                chartLabels.length = 0;
                
                // Берем последние 50 точек (чтобы после F5 масштаб/вид не "прыгал")
                const lastPoints = history.slice(-50);
                lastPoints.forEach(item => {
                    chartData.push(item.metrics.velocity_rms_mm_s);
                    chartLabels.push(toTimeLabel(item.timestamp));
                });
                
                // If less than 50 points, pad with zeros
                while (chartData.length < 50) {
                    chartData.unshift(0);
                    chartLabels.unshift('');
                }
                
                historyChart.update();
            } catch (e) {
                console.error('Failed to load history:', e);
            }
        }

        function updateNarrowbandChart(chart, metaId, flagId, spectrum) {
            if (!spectrum || !spectrum.freqs_mhz || !spectrum.bins) return;

            chart.data.labels = spectrum.freqs_mhz;
            chart.data.datasets[0].data = spectrum.bins;
            if (spectrum.peak_detected && typeof spectrum.peak_freq_mhz === 'number' && typeof spectrum.peak_power_dbm === 'number') {
                chart.data.datasets[1].data = [{ x: spectrum.peak_freq_mhz, y: spectrum.peak_power_dbm }];
            } else {
                chart.data.datasets[1].data = [];
            }
            chart.update();

            const metaEl = document.getElementById(metaId);
            const flagEl = document.getElementById(flagId);
            const noiseFloor = typeof spectrum.noise_floor_dbm === 'number' ? spectrum.noise_floor_dbm.toFixed(1) : '--';
            const peakPower = typeof spectrum.peak_power_dbm === 'number' ? spectrum.peak_power_dbm.toFixed(1) : '--';
            const peakDelta = typeof spectrum.peak_delta_db === 'number' ? spectrum.peak_delta_db.toFixed(1) : '--';
            const peakFreq = typeof spectrum.peak_freq_mhz === 'number' ? spectrum.peak_freq_mhz.toFixed(3) : '--';
            metaEl.textContent = `Noise floor: ${noiseFloor} dBm | Peak: ${peakPower} dBm @ ${peakFreq} MHz | Delta: ${peakDelta} dB`;

            if (spectrum.peak_detected) {
                flagEl.textContent = 'PEAK DETECTED';
                flagEl.classList.add('active');
            } else {
                flagEl.textContent = 'NO PEAK';
                flagEl.classList.remove('active');
            }
        }

        async function update() {
            try {
                const res = await fetch(API_URL);
                if (res.status === 404) {
                    consecutiveErrors = 0;
                    lastTelemetryAtMs = null;
                    setConnectionStatus('NO DATA', '#d29922');
                    return;
                }
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();

                consecutiveErrors = 0;
                // Свежесть связи определяем по моменту успешного ответа от API,
                // а не по timestamp с сервера, чтобы рассинхрон часов клиента и
                // Orange Pi не приводил к ложному OFFLINE.
                lastTelemetryAtMs = Date.now();
                updateConnectionBadge();

                // Update Threat
                const level = data.metrics.velocity_rms_mm_s; // Using this as RF Level
                const threatEl = document.getElementById('threatValue');
                const labelEl = document.querySelector('.gauge-label');
                threatEl.innerText = level.toFixed(1);
                
                // Update status label based on threat level
                if (level > 80) {
                    labelEl.innerText = "CRITICAL";
                    labelEl.style.color = "#f85149";
                } else if (level > 50) {
                    labelEl.innerText = "WARNING";
                    labelEl.style.color = "#d29922";
                } else {
                    labelEl.innerText = "SAFE";
                    labelEl.style.color = "#8b949e";
                }
                
                // Alert Logic
                document.body.classList.remove('alert-mode', 'warning-mode');
                
                if (level > 80) {
                    document.body.classList.add('alert-mode');
                    historyChart.data.datasets[0].borderColor = '#f85149';
                    historyChart.data.datasets[0].backgroundColor = 'rgba(248, 81, 73, 0.2)';
                } else if (level > 50) {
                    document.body.classList.add('warning-mode');
                    historyChart.data.datasets[0].borderColor = '#d29922';
                    historyChart.data.datasets[0].backgroundColor = 'rgba(210, 153, 34, 0.2)';
                } else {
                    historyChart.data.datasets[0].borderColor = '#2ea043';
                    historyChart.data.datasets[0].backgroundColor = 'rgba(46, 160, 67, 0.1)';
                }

                // Update Bars
                if (data.spectrum && data.spectrum.bins) {
                    const bins = data.spectrum.bins;
                    const visibleBins = bins.length >= 4 ? [bins[1], bins[3]] : bins;
                    visibleBins.forEach((val, idx) => {
                        if (idx < LABELS.length) {
                            document.getElementById(`val-${idx}`).innerText = val.toFixed(1);
                            document.getElementById(`bar-${idx}`).style.height = `${Math.min(val, 100)}%`;
                        }
                    });
                }

                if (data.spectrum && data.spectrum.narrowband_868_870) {
                    updateNarrowbandChart(live868Chart, 'live868Meta', 'live868PeakFlag', data.spectrum.narrowband_868_870);
                }

                if (data.spectrum && data.spectrum.narrowband_1279_1281) {
                    updateNarrowbandChart(live1280Chart, 'live1280Meta', 'live1280PeakFlag', data.spectrum.narrowband_1279_1281);
                }

                // Update Chart with telemetry timestamp (consistent with history)
                const timeLabel = toTimeLabel(data.timestamp);
                const chartData = historyChart.data.datasets[0].data;
                const chartLabels = historyChart.data.labels;
                
                chartData.shift();
                chartData.push(level);
                chartLabels.shift();
                chartLabels.push(timeLabel);
                
                historyChart.update();

            } catch (e) {
                console.error(e);
                consecutiveErrors += 1;
                updateConnectionBadge();
            }
        }

        // Load history first, then start live updates (prevents chart "jump" after F5)
        async function init() {
            await loadHistory();
            await update();
            setInterval(update, 1000);
        }

        init();
    </script>
</body>
</html>
    """
