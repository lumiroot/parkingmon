"""김해공항 주차장 모니터링 웹 대시보드."""

import json
import logging
from collections import defaultdict

from flask import Flask, render_template_string

import config
import db
from collector import collect_and_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>김해공항 주차장 모니터링</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            padding: 24px 32px;
            text-align: center;
        }
        .header h1 { font-size: 1.6rem; margin-bottom: 4px; }
        .header p { font-size: 0.9rem; opacity: 0.8; }
        .controls {
            display: flex;
            justify-content: center;
            gap: 8px;
            padding: 16px;
            flex-wrap: wrap;
        }
        .controls button {
            padding: 8px 20px;
            border: 2px solid #1a1a2e;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .controls button.active, .controls button:hover {
            background: #1a1a2e;
            color: white;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            padding: 0 24px 16px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .card h3 {
            font-size: 0.85rem;
            color: #666;
            margin-bottom: 8px;
        }
        .card .value {
            font-size: 2rem;
            font-weight: 700;
        }
        .card .sub {
            font-size: 0.8rem;
            color: #999;
            margin-top: 4px;
        }
        .card .bar {
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            margin-top: 12px;
            overflow: hidden;
        }
        .card .bar-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin: 0 24px 24px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .chart-container h2 {
            font-size: 1.1rem;
            margin-bottom: 16px;
        }
        .chart-wrapper {
            position: relative;
            height: 400px;
        }
        .no-data {
            text-align: center;
            padding: 60px 20px;
            color: #999;
            font-size: 1.1rem;
        }
        .last-collected {
            text-align: center;
            padding: 8px 24px 0;
            max-width: 1200px;
            margin: 0 auto;
            color: #888;
            font-size: 0.85rem;
        }
        .last-updated {
            text-align: center;
            padding: 8px;
            color: #999;
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>김해공항 주차장 모니터링</h1>
        <p>실시간 주차 가능 대수 추이</p>
    </div>

    <div class="controls">
        <button onclick="loadData(1)" id="btn-1h">1시간</button>
        <button onclick="loadData(6)" id="btn-6h">6시간</button>
        <button onclick="loadData(24)" class="active" id="btn-24h">24시간</button>
        <button onclick="loadData(72)" id="btn-72h">3일</button>
        <button onclick="loadData(168)" id="btn-168h">7일</button>
        <button onclick="collectNow()" id="btn-collect" style="border-color:#e15759;color:#e15759;margin-left:16px">수집 실행</button>
    </div>

    <div class="last-collected" id="lastCollected"></div>
    <div class="summary" id="summary"></div>

    <div class="chart-container">
        <h2>주차 가능 대수 추이</h2>
        <div class="chart-wrapper">
            <canvas id="availableChart"></canvas>
        </div>
    </div>

    <div class="chart-container">
        <h2>점유율 추이 (%)</h2>
        <div class="chart-wrapper">
            <canvas id="occupancyChart"></canvas>
        </div>
    </div>

    <div class="last-updated" id="lastUpdated"></div>

    <script>
    const COLORS = [
        '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
        '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
    ];

    let availableChart = null;
    let occupancyChart = null;
    let currentHours = 24;

    function getColor(i) { return COLORS[i % COLORS.length]; }

    function getBarColor(ratio) {
        if (ratio >= 0.9) return '#e15759';
        if (ratio >= 0.7) return '#f28e2b';
        return '#59a14f';
    }

    function renderSummary(latest) {
        const el = document.getElementById('summary');
        if (!latest || latest.length === 0) {
            el.innerHTML = '<div class="no-data">데이터가 없습니다. 수집이 시작되면 여기에 현황이 표시됩니다.</div>';
            return;
        }
        el.innerHTML = latest.map(p => {
            const ratio = p.total_spaces > 0 ? p.occupied_spaces / p.total_spaces : 0;
            const pct = (ratio * 100).toFixed(1);
            const color = getBarColor(ratio);
            return `
                <div class="card">
                    <h3>${p.parking_name}</h3>
                    <div class="value" style="color:${color}">${p.available_spaces}</div>
                    <div class="sub">주차가능 / 전체 ${p.total_spaces}면 (점유 ${pct}%)</div>
                    <div class="bar">
                        <div class="bar-fill" style="width:${pct}%;background:${color}"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderCharts(data) {
        // Group by parking_name
        const grouped = {};
        data.forEach(r => {
            if (!grouped[r.parking_name]) grouped[r.parking_name] = [];
            grouped[r.parking_name].push(r);
        });

        const names = Object.keys(grouped).sort();

        // Available chart
        const availableDatasets = names.map((name, i) => ({
            label: name,
            data: grouped[name].map(r => ({
                x: new Date(r.collected_at),
                y: r.available_spaces,
            })),
            borderColor: getColor(i),
            backgroundColor: getColor(i) + '20',
            borderWidth: 2,
            pointRadius: 1.5,
            tension: 0.3,
            fill: false,
        }));

        // Occupancy chart
        const occupancyDatasets = names.map((name, i) => ({
            label: name,
            data: grouped[name].map(r => ({
                x: new Date(r.collected_at),
                y: r.total_spaces > 0
                    ? ((r.occupied_spaces / r.total_spaces) * 100).toFixed(1)
                    : 0,
            })),
            borderColor: getColor(i),
            backgroundColor: getColor(i) + '20',
            borderWidth: 2,
            pointRadius: 1.5,
            tension: 0.3,
            fill: false,
        }));

        const timeOpts = {
            type: 'time',
            time: {
                tooltipFormat: 'MM/dd HH:mm',
                displayFormats: { hour: 'HH:mm', day: 'MM/dd' },
            },
            title: { display: true, text: '시간' },
        };

        if (availableChart) availableChart.destroy();
        if (occupancyChart) occupancyChart.destroy();

        availableChart = new Chart(document.getElementById('availableChart'), {
            type: 'line',
            data: { datasets: availableDatasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: timeOpts,
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: '주차 가능 대수' },
                    },
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { mode: 'index', intersect: false },
                },
                interaction: { mode: 'nearest', axis: 'x', intersect: false },
            },
        });

        occupancyChart = new Chart(document.getElementById('occupancyChart'), {
            type: 'line',
            data: { datasets: occupancyDatasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: timeOpts,
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: '점유율 (%)' },
                    },
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { mode: 'index', intersect: false },
                },
                interaction: { mode: 'nearest', axis: 'x', intersect: false },
            },
        });
    }

    async function loadData(hours) {
        currentHours = hours || currentHours;

        document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
        const btn = document.getElementById('btn-' + currentHours + 'h');
        if (btn) btn.classList.add('active');

        try {
            const [recordsResp, latestResp] = await Promise.all([
                fetch('/api/records?hours=' + currentHours),
                fetch('/api/latest'),
            ]);
            const records = await recordsResp.json();
            const latest = await latestResp.json();

            renderSummary(latest);
            renderCharts(records);

            if (latest.length > 0) {
                const t = new Date(latest[0].collected_at);
                const timeStr = t.toLocaleString('ko-KR');
                document.getElementById('lastCollected').textContent =
                    '마지막 수집: ' + timeStr;
                document.getElementById('lastUpdated').textContent =
                    '마지막 업데이트: ' + timeStr;
            }
        } catch (e) {
            console.error('데이터 로드 실패:', e);
        }
    }

    async function collectNow() {
        const btn = document.getElementById('btn-collect');
        btn.disabled = true;
        btn.textContent = '수집 중...';
        try {
            const resp = await fetch('/api/collect', { method: 'POST' });
            const result = await resp.json();
            if (result.error) {
                alert('수집 실패: ' + result.error);
            } else {
                btn.textContent = result.count + '개 수집 완료';
                await loadData();
            }
        } catch (e) {
            alert('수집 요청 실패: ' + e);
        } finally {
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = '수집 실행';
            }, 2000);
        }
    }

    // 초기 로드 및 자동 새로고침 (60초)
    loadData(24);
    setInterval(() => loadData(), 60000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/records")
def api_records():
    from flask import request

    hours = int(request.args.get("hours", 24))
    parking_name = request.args.get("parking_name")
    records = db.get_records(hours=hours, parking_name=parking_name)
    return json.dumps(records, ensure_ascii=False)


@app.route("/api/latest")
def api_latest():
    records = db.get_latest_records()
    return json.dumps(records, ensure_ascii=False)


@app.route("/api/parking_names")
def api_parking_names():
    names = db.get_parking_names()
    return json.dumps(names, ensure_ascii=False)


@app.route("/api/collect", methods=["POST"])
def api_collect():
    try:
        count = collect_and_store()
        return json.dumps({"count": count}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False), 500
