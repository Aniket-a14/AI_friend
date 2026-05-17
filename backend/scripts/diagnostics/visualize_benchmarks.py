#!/usr/bin/env python3
"""
AI Friend Benchmark Visualizer
Parses stored JSON benchmark history files and generates a premium, 
self-contained, interactive HTML dashboard using Chart.js.
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
    <title>AI Friend - Benchmark Analytics Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #0b0f19;
            --bg-secondary: #161d30;
            --bg-tertiary: #1f2942;
            --accent-primary: #3b82f6;
            --accent-secondary: #10b981;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --border-color: #2d3748;
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
            padding: 2rem;
            line-height: 1.5;
        }

        header {
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }

        h1 {
            font-size: 2.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 1rem;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .card {
            background-color: var(--bg-secondary);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }

        .card h2 {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--accent-primary);
            padding-left: 0.75rem;
        }

        .chart-container {
            position: relative;
            height: 350px;
            width: 100%;
        }

        .table-container {
            overflow-x: auto;
            margin-top: 1rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }

        th {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            font-weight: 600;
            padding: 0.75rem 1rem;
            border-bottom: 2px solid var(--border-color);
        }

        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }

        tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-primary);
        }

        .badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-ops {
            background-color: rgba(16, 185, 129, 0.1);
            color: var(--accent-secondary);
        }

        .badge-time {
            background-color: rgba(59, 130, 246, 0.1);
            color: var(--accent-primary);
        }
    </style>
</head>
<body>

    <header>
        <h1>AI Friend Analytics</h1>
        <div class="subtitle">Interactive performance benchmark history and latency profiling</div>
    </header>

    <div class="grid">
        <!-- Latency Chart -->
        <div class="card">
            <h2>Average Execution Latency (Lower is Better)</h2>
            <div class="chart-container">
                <canvas id="latencyChart"></canvas>
            </div>
        </div>

        <!-- Throughput Chart -->
        <div class="card">
            <h2>System Throughput (Operations/Sec - Higher is Better)</h2>
            <div class="chart-container">
                <canvas id="throughputChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Data Table Card -->
    <div class="card">
        <h2>Detailed Runs History</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Run ID</th>
                        <th>Timestamp</th>
                        <th>Test Name</th>
                        <th>Min (μs)</th>
                        <th>Max (μs)</th>
                        <th>Mean (μs)</th>
                        <th>Median (μs)</th>
                        <th>Throughput (OPS)</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    <!-- Dynamic Rows -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const runData = /*DATA_PLACEHOLDER*/;

        // Sort data chronologically by timestamp
        runData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Group data by test name
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
            tests[item.test_name].means.push((item.mean * 1000000).toFixed(2)); // convert to microseconds
            tests[item.test_name].ops.push(item.ops.toFixed(0));
            tests[item.test_name].dates.push(item.timestamp.split('T')[0]);
        });

        const testNames = Object.keys(tests);

        // Render Latency Chart
        const ctxLatency = document.getElementById('latencyChart').getContext('2d');
        const latencyDatasets = testNames.map((name, index) => {
            const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
            return {
                label: name.replace('test_', ''),
                data: tests[name].means,
                borderColor: colors[index % colors.length],
                backgroundColor: colors[index % colors.length] + '20',
                borderWidth: 3,
                tension: 0.3,
                fill: true
            };
        });

        // Use the dates of the first test as labels
        const labels = tests[testNames[0]] ? tests[testNames[0]].runs.map((id, idx) => `Run #${id} (${tests[testNames[0]].dates[idx]})`) : [];

        new Chart(ctxLatency, {
            type: 'line',
            data: {
                labels: labels,
                datasets: latencyDatasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#9ca3af' } }
                },
                scales: {
                    y: {
                        grid: { color: '#2d3748' },
                        ticks: { color: '#9ca3af' },
                        title: { display: true, text: 'Mean Time (μs)', color: '#9ca3af' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#9ca3af' }
                    }
                }
            }
        });

        // Render Throughput Chart
        const ctxThroughput = document.getElementById('throughputChart').getContext('2d');
        const throughputDatasets = testNames.map((name, index) => {
            const colors = ['#10b981', '#3b82f6', '#ef4444', '#f59e0b'];
            return {
                label: name.replace('test_', ''),
                data: tests[name].ops,
                borderColor: colors[index % colors.length],
                backgroundColor: colors[index % colors.length] + '20',
                borderWidth: 3,
                tension: 0.3,
                fill: true
            };
        });

        new Chart(ctxThroughput, {
            type: 'line',
            data: {
                labels: labels,
                datasets: throughputDatasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#9ca3af' } }
                },
                scales: {
                    y: {
                        grid: { color: '#2d3748' },
                        ticks: { color: '#9ca3af' },
                        title: { display: true, text: 'Operations / Sec (OPS)', color: '#9ca3af' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#9ca3af' }
                    }
                }
            }
        });

        // Populate Table
        const tableBody = document.getElementById('tableBody');
        runData.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>#${item.run_id}</strong></td>
                <td>${item.timestamp.replace('T', ' ').split('.')[0]}</td>
                <td>${item.test_name}</td>
                <td>${(item.min * 1000000).toFixed(1)}</td>
                <td>${(item.max * 1000000).toFixed(1)}</td>
                <td><span class="badge badge-time">${(item.mean * 1000000).toFixed(1)} μs</span></td>
                <td>${(item.median * 1000000).toFixed(1)}</td>
                <td><span class="badge badge-ops">${item.ops.toLocaleString(undefined, {maximumFractionDigits: 0})} OPS</span></td>
            `;
            tableBody.appendChild(row);
        });
    </script>
</body>
</html>
"""


def load_benchmarks():
    benchmark_files = glob(str(BENCHMARKS_DIR / "**/*.json"), recursive=True)
    if not benchmark_files:
        print("⚠️ No benchmark JSON files found in .benchmarks/ directory.")
        return []

    # Sort files by their name index (e.g. 0001_, 0002_)
    benchmark_files.sort(key=lambda x: os.path.basename(x))

    all_runs = []
    for filepath in benchmark_files:
        filename = os.path.basename(filepath)
        # Extract run index (e.g. "0001" from "0001_xxxx.json")
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

    compiled_html = HTML_TEMPLATE.replace("/*DATA_PLACEHOLDER*/", json.dumps(runs))

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(compiled_html)

    print(f"✨ Success! Interactive dashboard written to: {OUTPUT_HTML.absolute()}")
    print("🚀 You can now double-click this file or open it in your browser!")


if __name__ == "__main__":
    main()
