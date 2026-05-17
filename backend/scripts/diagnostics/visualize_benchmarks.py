"""
AI Friend Industrial Benchmark Visualizer
Parses stored JSON benchmark history files and generates a premium, 
Grafana-style, interactive HTML analytics dashboard using Chart.js.
"""

import json
import os
from glob import glob
from pathlib import Path

# Resolve root paths
BACKEND_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_DIR = BACKEND_ROOT / ".benchmarks"
OUTPUT_HTML = BACKEND_ROOT / "benchmark_report.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Friend - Industrial Performance Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #070913;
            --bg-secondary: #0f1322;
            --bg-card: #151b30;
            --bg-card-hover: #1c2440;
            --accent-primary: #3b82f6;
            --accent-success: #10b981;
            --accent-warning: #f59e0b;
            --accent-critical: #ef4444;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --border-color: #242f4c;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 2.5rem;
            line-height: 1.6;
        }

        header {
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 1rem;
        }

        /* Filter Controls */
        .controls-container {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }

        .btn-filter {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.5rem 1.25rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }

        .btn-filter:hover {
            border-color: var(--accent-primary);
            color: var(--text-primary);
            background-color: var(--bg-card-hover);
        }

        .btn-filter.active {
            background-color: var(--accent-primary);
            color: white;
            border-color: var(--accent-primary);
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
        }

        /* KPI Cards Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .kpi-card {
            background-color: var(--bg-card);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
            border-color: #3b82f640;
        }

        .kpi-title {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .kpi-value {
            font-size: 1.75rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            margin-bottom: 0.5rem;
        }

        .kpi-grade {
            display: inline-block;
            align-self: flex-start;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .grade-opt { background-color: rgba(16, 185, 129, 0.1); color: var(--accent-success); }
        .grade-warn { background-color: rgba(245, 158, 11, 0.1); color: var(--accent-warning); }
        .grade-crit { background-color: rgba(239, 68, 68, 0.1); color: var(--accent-critical); }

        /* Main Chart Panels */
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 2rem;
            margin-bottom: 2.5rem;
        }

        .panel-card {
            background-color: var(--bg-card);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 2rem;
        }

        .panel-card h2 {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--accent-primary);
            padding-left: 0.75rem;
        }

        .chart-container {
            position: relative;
            height: 380px;
            width: 100%;
        }

        /* Data Tables */
        .data-card {
            background-color: var(--bg-card);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 2rem;
        }

        .table-header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            font-weight: 600;
            padding: 1rem;
            border-bottom: 2px solid var(--border-color);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }

        td {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }

        tr:hover td {
            background-color: rgba(255, 255, 255, 0.015);
            color: var(--text-primary);
        }

        .badge-kpi {
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
</head>
<body>

    <header>
        <div>
            <h1>AI Friend Performance Hub</h1>
            <div class="subtitle">Grafana-style cognitive, memory, and voice pipeline performance metrics</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 0.875rem; color: var(--text-secondary);">Last Generated</div>
            <div style="font-family: 'JetBrains Mono'; font-weight: 600; color: var(--accent-success);" id="genTime">--</div>
        </div>
    </header>

    <!-- Pipeline Filters -->
    <div class="controls-container">
        <button class="btn-filter active" onclick="filterPipeline('all', this)">🧠 Full Brain (All)</button>
        <button class="btn-filter" onclick="filterPipeline('telemetry', this)">⚡ Telemetry Loop</button>
        <button class="btn-filter" onclick="filterPipeline('cognitive', this)">👁️ Cognitive State</button>
        <button class="btn-filter" onclick="filterPipeline('memory', this)">📁 Memory & NLP</button>
        <button class="btn-filter" onclick="filterPipeline('voice', this)">🗣️ Voice & Audio</button>
    </div>

    <!-- KPI Grade Grid -->
    <div class="kpi-grid" id="kpiGrid">
        <!-- Dyn KPI Cards -->
    </div>

    <!-- Charts -->
    <div class="chart-grid">
        <div class="panel-card">
            <h2>Execution Latency Trend (Lower is Better)</h2>
            <div class="chart-container">
                <canvas id="latencyChart"></canvas>
            </div>
        </div>

        <div class="panel-card">
            <h2>Operations Throughput (OPS - Higher is Better)</h2>
            <div class="chart-container">
                <canvas id="throughputChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Data Tables -->
    <div class="data-card">
        <div class="table-header-container">
            <h2>Historical Engineering Runs</h2>
        </div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Run</th>
                        <th>Timestamp</th>
                        <th>Subsystem Metric</th>
                        <th>Min Latency</th>
                        <th>Mean Latency</th>
                        <th>Max Latency</th>
                        <th>StdDev</th>
                        <th>Throughput (OPS)</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    <!-- Dyn rows -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const runData = /*DATA_PLACEHOLDER*/;

        // Document Generation Timestamp
        if (runData.length > 0) {
            document.getElementById('genTime').innerText = runData[runData.length - 1].timestamp.replace('T', ' ').split('.')[0];
        }

        // Mapping metrics to specific pipeline groups
        const pipelineMap = {
            'test_async_telemetry_queue_put_benchmark': 'telemetry',
            'test_subject_metrics_record_benchmark': 'telemetry',
            'test_identity_appraisal_benchmark': 'cognitive',
            'test_reappraisal_cognitive_benchmark': 'cognitive',
            'test_subconscious_threat_scan_benchmark': 'cognitive',
            'test_arbitration_layer_benchmark': 'cognitive',
            'test_endocrine_state_decay_benchmark': 'cognitive',
            'test_personality_modulation_benchmark': 'cognitive',
            'test_decision_tree_walk_benchmark': 'cognitive',
            'test_pipeline_step_dispatch_benchmark': 'cognitive',
            'test_nats_metadata_serialization_benchmark': 'cognitive',
            'test_memory_semantic_retrieve_benchmark': 'memory',
            'test_triple_extractor_nlp_benchmark': 'memory',
            'test_conversation_serialization_benchmark': 'memory',
            'test_hybrid_segmenter_benchmark': 'memory',
            'test_audio_normalizer_16bit_pcm_benchmark': 'voice'
        };

        // Classify Health Grades
        function getGrade(meanSec) {
            const ms = meanSec * 1000;
            if (ms < 1.0) return { label: 'Optimized (Sub-ms)', class: 'grade-opt' };
            if (ms < 15.0) return { label: 'Warning', class: 'grade-warn' };
            return { label: 'Critical Hotpath', class: 'grade-crit' };
        }

        // Populate KPI Cards
        function populateKPIs(filteredRuns) {
            const kpiGrid = document.getElementById('kpiGrid');
            kpiGrid.innerHTML = '';
            
            // Group by test name, take the latest run
            const latest = {};
            filteredRuns.forEach(run => {
                latest[run.test_name] = run;
            });

            const keys = Object.keys(latest);
            // Limit to at most 4 KPI cards to preserve dashboard grid visual balance
            keys.slice(0, 4).forEach(testName => {
                const item = latest[testName];
                const grade = getGrade(item.mean);
                const displayVal = (item.mean * 1000) < 1.0 
                    ? (item.mean * 1000000).toFixed(1) + ' μs' 
                    : (item.mean * 1000).toFixed(2) + ' ms';

                const card = document.createElement('div');
                card.className = 'kpi-card';
                card.innerHTML = `
                    <div>
                        <div class="kpi-title">${item.test_name.replace('test_', '').replace('_benchmark', '').replace(/_/g, ' ')}</div>
                        <div class="kpi-value">${displayVal}</div>
                    </div>
                    <span class="kpi-grade ${grade.class}">${grade.label}</span>
                `;
                kpiGrid.appendChild(card);
            });
        }

        // Chronological sort
        runData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Group runs
        const tests = {};
        runData.forEach(item => {
            if (!tests[item.test_name]) {
                tests[item.test_name] = {
                    runs: [],
                    means: [],
                    ops: [],
                    dates: []
                };
            }
            tests[item.test_name].runs.push(item.run_id);
            tests[item.test_name].means.push((item.mean * 1000).toFixed(3)); // ms
            tests[item.test_name].ops.push(item.ops.toFixed(0));
            tests[item.test_name].dates.push(item.timestamp.split('T')[0]);
        });

        const testNames = Object.keys(tests);
        const uniqueRuns = [...new Set(runData.map(item => `Run #${item.run_id}`))];

        // Chart.js references
        let latencyChart = null;
        let throughputChart = null;

        function renderCharts(filterGroup = 'all') {
            const datasetsLatency = [];
            const datasetsThroughput = [];

            const colors = [
                '#3b82f6', '#10b981', '#f59e0b', '#ef4444', 
                '#8b5cf6', '#ec4899', '#06b6d4', '#14b8a6', 
                '#f43f5e', '#a855f7', '#6366f1', '#eab308'
            ];

            let colorIdx = 0;
            testNames.forEach(name => {
                const group = pipelineMap[name] || 'cognitive';
                if (filterGroup !== 'all' && group !== filterGroup) return;

                const color = colors[colorIdx % colors.length];
                colorIdx++;

                datasetsLatency.push({
                    label: name.replace('test_', '').replace('_benchmark', ''),
                    data: tests[name].means,
                    borderColor: color,
                    backgroundColor: color + '10',
                    borderWidth: 2.5,
                    tension: 0.25,
                    fill: false
                });

                datasetsThroughput.push({
                    label: name.replace('test_', '').replace('_benchmark', ''),
                    data: tests[name].ops,
                    borderColor: color,
                    backgroundColor: color + '10',
                    borderWidth: 2.5,
                    tension: 0.25,
                    fill: false
                });
            });

            if (latencyChart) latencyChart.destroy();
            if (throughputChart) throughputChart.destroy();

            const ctxL = document.getElementById('latencyChart').getContext('2d');
            latencyChart = new Chart(ctxL, {
                type: 'line',
                data: { labels: uniqueRuns, datasets: datasetsLatency },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#9ca3af', font: { size: 10 } } } },
                    scales: {
                        y: { grid: { color: '#1e293b' }, ticks: { color: '#9ca3af' }, title: { display: true, text: 'Mean Time (ms)', color: '#9ca3af' } },
                        x: { grid: { display: false }, ticks: { color: '#9ca3af' } }
                    }
                }
            });

            const ctxT = document.getElementById('throughputChart').getContext('2d');
            throughputChart = new Chart(ctxT, {
                type: 'line',
                data: { labels: uniqueRuns, datasets: datasetsThroughput },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#9ca3af', font: { size: 10 } } } },
                    scales: {
                        y: { grid: { color: '#1e293b' }, ticks: { color: '#9ca3af' }, title: { display: true, text: 'OPS (Trans / Sec)', color: '#9ca3af' } },
                        x: { grid: { display: false }, ticks: { color: '#9ca3af' } }
                    }
                }
            });
        }

        // Render Data Table rows
        function populateTable(filterGroup = 'all') {
            const tableBody = document.getElementById('tableBody');
            tableBody.innerHTML = '';

            runData.forEach(item => {
                const group = pipelineMap[item.test_name] || 'cognitive';
                if (filterGroup !== 'all' && group !== filterGroup) return;

                const row = document.createElement('tr');
                const meanVal = (item.mean * 1000) < 1.0 
                    ? (item.mean * 1000000).toFixed(1) + ' μs' 
                    : (item.mean * 1000).toFixed(3) + ' ms';

                row.innerHTML = `
                    <td><strong>#${item.run_id}</strong></td>
                    <td>${item.timestamp.replace('T', ' ').split('.')[0]}</td>
                    <td style="color: var(--text-primary); font-weight: 500;">${item.test_name}</td>
                    <td>${(item.min * 1000).toFixed(3)} ms</td>
                    <td><span class="badge-kpi grade-opt">${meanVal}</span></td>
                    <td>${(item.max * 1000).toFixed(3)} ms</td>
                    <td>${(item.stddev * 1000).toFixed(3)} ms</td>
                    <td><span class="badge-kpi grade-warn">${item.ops.toLocaleString(undefined, {maximumFractionDigits: 0})} OPS</span></td>
                `;
                tableBody.appendChild(row);
            });
        }

        // Filter Action
        function filterPipeline(group, btn) {
            // Remove active classes
            document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Re-render components
            const filteredRuns = runData.filter(item => group === 'all' || (pipelineMap[item.test_name] || 'cognitive') === group);
            populateKPIs(filteredRuns);
            renderCharts(group);
            populateTable(group);
        }

        // Initial Boot
        populateKPIs(runData);
        renderCharts('all');
        populateTable('all');
    </script>
</body>
</html>
"""


def load_benchmarks():
    benchmark_files = glob(str(BENCHMARKS_DIR / "**/*.json"), recursive=True)
    if not benchmark_files:
        print("⚠️ No benchmark JSON files found in .benchmarks/ directory.")
        return []

    benchmark_files.sort(key=lambda x: os.path.basename(x))

    all_runs = []
    for filepath in benchmark_files:
        filename = os.path.basename(filepath)
        try:
            run_id = int(filename.split("_")[0])
        except ValueError:
            run_id = filename

        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error parsing {filename}: {e}")
                continue

            timestamp = data.get("datetime", "")
            benchmarks = data.get("benchmarks", [])

            for bench in benchmarks:
                all_runs.append(
                    {
                        "run_id": run_id,
                        "timestamp": timestamp,
                        "test_name": bench.get("name", "unknown"),
                        "min": bench.get("stats", {}).get("min", 0),
                        "max": bench.get("stats", {}).get("max", 0),
                        "mean": bench.get("stats", {}).get("mean", 0),
                        "median": bench.get("stats", {}).get("median", 0),
                        "stddev": bench.get("stats", {}).get("stddev", 0),
                        "ops": bench.get("stats", {}).get("ops", 0),
                    }
                )

    return all_runs


def main():
    print("🔍 Extracting historical benchmark runs...")
    runs = load_benchmarks()

    if not runs:
        print("❌ Cannot compile report: No benchmark data available.")
        return

    print(f"📊 Compiling Grafana-grade analytics dashboard...")
    compiled_html = HTML_TEMPLATE.replace("/*DATA_PLACEHOLDER*/", json.dumps(runs))

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(compiled_html)

    print(f"✨ Success! Upgraded industrial dashboard written to: {OUTPUT_HTML.absolute()}")
    print("🚀 You can now double-click this file or open it in your browser!")


if __name__ == "__main__":
    main()
