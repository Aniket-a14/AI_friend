#!/usr/bin/env python3
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
    <title>AI Friend - Performance Analytics Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #05070f;
            --bg-secondary: #0a0d1d;
            --bg-card: rgba(16, 22, 47, 0.7);
            --bg-card-hover: rgba(26, 35, 75, 0.9);
            --accent-primary: #3b82f6;
            --accent-success: #10b981;
            --accent-warning: #f59e0b;
            --accent-critical: #ef4444;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --border-color: rgba(59, 130, 246, 0.15);
            --border-glow: rgba(59, 130, 246, 0.3);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
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

        /* Tabs Navigation */
        .tabs-nav {
            display: flex;
            gap: 0.5rem;
            background-color: var(--bg-secondary);
            padding: 0.4rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            margin-bottom: 2rem;
            width: fit-content;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 0.6rem 1.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }

        .tab-btn:hover {
            color: var(--text-primary);
            background-color: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            background-color: var(--accent-primary);
            color: white;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        /* Cognitive Brain Flow Map */
        .brain-section {
            background-color: var(--bg-secondary);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 2rem;
            margin-bottom: 2.5rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        }

        .section-header {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--accent-primary);
            padding-left: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* SVG Pipeline Tree Styling */
        .brain-flow-map {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-around;
            align-items: center;
            gap: 1.5rem;
            padding: 1.5rem;
            background-color: rgba(255, 255, 255, 0.01);
            border-radius: 0.75rem;
            border: 1px dashed rgba(59, 130, 246, 0.1);
        }

        .brain-node {
            background-color: var(--bg-card);
            border: 2px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem;
            min-width: 170px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
            position: relative;
        }

        .brain-node:hover {
            transform: scale(1.05) translateY(-3px);
            box-shadow: 0 8px 20px rgba(59, 130, 246, 0.25);
        }

        .brain-node.active-inspect {
            border-color: var(--accent-primary) !important;
            box-shadow: 0 0 15px var(--border-glow);
        }

        .node-name {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .node-latency {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            font-weight: 700;
        }

        .node-flow-arrow {
            color: var(--accent-primary);
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            user-select: none;
        }

        @media (max-width: 768px) {
            .node-flow-arrow {
                transform: rotate(90deg);
            }
        }

        /* Color classes for Node Grades */
        .node-opt { border-color: var(--accent-success); color: var(--accent-success); background-color: rgba(16, 185, 129, 0.04); }
        .node-warn { border-color: var(--accent-warning); color: var(--accent-warning); background-color: rgba(245, 158, 11, 0.04); }
        .node-crit { border-color: var(--accent-critical); color: var(--accent-critical); background-color: rgba(239, 68, 68, 0.04); }

        /* KPI Display Panel */
        .inspect-panel {
            margin-top: 1.5rem;
            padding: 1.25rem;
            border-radius: 0.75rem;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            display: none;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .inspect-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
        }

        .inspect-kpi {
            display: flex;
            flex-direction: column;
        }

        .inspect-title {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .inspect-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        /* Dynamic Visualizer Grid */
        .visualizer-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
            margin-bottom: 2.5rem;
        }

        @media (max-width: 1200px) {
            .visualizer-grid {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background-color: var(--bg-secondary);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }

        .chart-container {
            position: relative;
            height: 380px;
            width: 100%;
        }

        /* Metrics list ranking table */
        .ranking-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }

        .ranking-item {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: border-color 0.2s ease;
        }

        .ranking-item:hover {
            border-color: var(--accent-primary);
        }

        .ranking-meta {
            display: flex;
            flex-direction: column;
        }

        .ranking-name {
            font-size: 0.85rem;
            font-weight: 600;
        }

        .ranking-ops {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .ranking-val {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 0.9rem;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
        }

        /* Historical Table Card */
        .table-card {
            background-color: var(--bg-secondary);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            padding: 2rem;
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
            background-color: rgba(255, 255, 255, 0.02);
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

        .badge-opt { background-color: rgba(16, 185, 129, 0.1); color: var(--accent-success); }
        .badge-warn { background-color: rgba(245, 158, 11, 0.1); color: var(--accent-warning); }
        .badge-crit { background-color: rgba(239, 68, 68, 0.1); color: var(--accent-critical); }
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

    <!-- 🧠 Cognitive Brain Process flow map -->
    <div class="brain-section">
        <div class="section-header">
            <span>🧠 Dynamic Brain Pipeline Process Map</span>
            <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-secondary);">Click any step to inspect hardware load and OPS throughput</span>
        </div>
        <div class="brain-flow-map">
            <!-- Node 1: Audio Ingest -->
            <div class="brain-node" id="node-audio" onclick="inspectNode('test_audio_normalizer_16bit_pcm_benchmark')">
                <div class="node-name">1. Audio Normalizer</div>
                <div class="node-latency" id="val-audio">--</div>
            </div>
            <div class="node-flow-arrow">➔</div>

            <!-- Node 2: Segmenter -->
            <div class="brain-node" id="node-segmenter" onclick="inspectNode('test_hybrid_segmenter_benchmark')">
                <div class="node-name">2. Text Segmenter</div>
                <div class="node-latency" id="val-segmenter">--</div>
            </div>
            <div class="node-flow-arrow">➔</div>

            <!-- Node 3: Threat Scan -->
            <div class="brain-node" id="node-threat" onclick="inspectNode('test_subconscious_threat_scan_benchmark')">
                <div class="node-name">3. Threat Scan</div>
                <div class="node-latency" id="val-threat">--</div>
            </div>
            <div class="node-flow-arrow">➔</div>

            <!-- Node 4: ACT-R Retrieve -->
            <div class="brain-node" id="node-memory" onclick="inspectNode('test_memory_semantic_retrieve_benchmark')">
                <div class="node-name">4. Memory Search</div>
                <div class="node-latency" id="val-memory">--</div>
            </div>
            <div class="node-flow-arrow">➔</div>

            <!-- Node 5: State Decay -->
            <div class="brain-node" id="node-hormone" onclick="inspectNode('test_endocrine_state_decay_benchmark')">
                <div class="node-name">5. Hormonal state</div>
                <div class="node-latency" id="val-hormone">--</div>
            </div>
            <div class="node-flow-arrow">➔</div>

            <!-- Node 6: Modulation -->
            <div class="brain-node" id="node-modulate" onclick="inspectNode('test_personality_modulation_benchmark')">
                <div class="node-name">6. LLM Modulation</div>
                <div class="node-latency" id="val-modulate">--</div>
            </div>
        </div>

        <!-- Node inspector side panel -->
        <div class="inspect-panel" id="inspectPanel">
            <h3 style="margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;" id="inspectName">Component Stats</h3>
            <div class="inspect-grid">
                <div class="inspect-kpi">
                    <span class="inspect-title">Subsystem Latency (Mean)</span>
                    <span class="inspect-value" id="inspectLatency">--</span>
                </div>
                <div class="inspect-kpi">
                    <span class="inspect-title">Operations Throughput</span>
                    <span class="inspect-value" id="inspectOPS" style="color: var(--accent-success);">--</span>
                </div>
                <div class="inspect-kpi">
                    <span class="inspect-title">Variance (StdDev)</span>
                    <span class="inspect-value" id="inspectStdDev">--</span>
                </div>
                <div class="inspect-kpi">
                    <span class="inspect-title">Observability overhead</span>
                    <span class="inspect-value" style="color: var(--accent-primary);">Async Buffered</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Category Tabs Navigation -->
    <div class="tabs-nav">
        <button class="tab-btn active" onclick="switchPipeline('telemetry', this)">⚡ Telemetry Loop</button>
        <button class="tab-btn" onclick="switchPipeline('cognitive', this)">🧠 Cognitive Brain</button>
        <button class="tab-btn" onclick="switchPipeline('memory', this)">📁 Memory & NLP</button>
        <button class="tab-btn" onclick="switchPipeline('voice', this)">🗣️ Voice Core</button>
    </div>

    <!-- Dynamic Visualizer Grid -->
    <div class="visualizer-grid">
        <!-- Main Line Chart Card -->
        <div class="card">
            <h2 id="chartTitle" style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; border-left: 4px solid var(--accent-primary); padding-left: 0.75rem;">⚡ Telemetry Loop Latency Trend</h2>
            <div class="chart-container">
                <canvas id="categoryChart"></canvas>
            </div>
        </div>

        <!-- Horizontal Bar Card (OPS ranking for latest run) -->
        <div class="card" style="display: flex; flex-direction: column;">
            <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; border-left: 4px solid var(--accent-success); padding-left: 0.75rem;">⚡ Throughput Rankings</h2>
            <div class="ranking-list" id="rankingList">
                <!-- Dynamically populated rank cards -->
            </div>
        </div>
    </div>

    <!-- Historical Data Card -->
    <div class="table-card">
        <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; border-left: 4px solid #f59e0b; padding-left: 0.75rem;">Run Ledger</h2>
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

        // Sort runs chronologically
        runData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        if (runData.length > 0) {
            document.getElementById('genTime').innerText = runData[runData.length - 1].timestamp.replace('T', ' ').split('.')[0];
        }

        // Exact Metric to Pipeline mapping
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

        const niceNames = {
            'test_async_telemetry_queue_put_benchmark': 'Telemetry Ingestion',
            'test_subject_metrics_record_benchmark': 'End-to-End Logger',
            'test_identity_appraisal_benchmark': 'Identity Appraisal',
            'test_reappraisal_cognitive_benchmark': 'Coping Reappraisal',
            'test_subconscious_threat_scan_benchmark': 'Subconscious Threat Scan',
            'test_arbitration_layer_benchmark': 'Arbitration Decision',
            'test_endocrine_state_decay_benchmark': 'Hormone Stress Decay',
            'test_personality_modulation_benchmark': 'LLM Temp Modulation',
            'test_decision_tree_walk_benchmark': 'BT Decision Tree',
            'test_pipeline_step_dispatch_benchmark': 'Step Router Loop',
            'test_nats_metadata_serialization_benchmark': 'Payload Serialization',
            'test_memory_semantic_retrieve_benchmark': 'ACT-R Retrieval Search',
            'test_triple_extractor_nlp_benchmark': 'NLP Knowledge Triples',
            'test_conversation_serialization_benchmark': 'Context Serialization',
            'test_hybrid_segmenter_benchmark': 'Hybrid Segmenter',
            'test_audio_normalizer_16bit_pcm_benchmark': 'Audio Normalizer'
        };

        // Extract latest run values to style the Dynamic Brain flow map
        function populateBrainMap() {
            const latest = {};
            runData.forEach(item => {
                latest[item.test_name] = item;
            });

            // Map UI steps to test metrics
            const steps = {
                'audio': latest['test_audio_normalizer_16bit_pcm_benchmark'],
                'segmenter': latest['test_hybrid_segmenter_benchmark'],
                'threat': latest['test_subconscious_threat_scan_benchmark'],
                'memory': latest['test_memory_semantic_retrieve_benchmark'],
                'hormone': latest['test_endocrine_state_decay_benchmark'],
                'modulate': latest['test_personality_modulation_benchmark']
            };

            for (const [id, run] of Object.entries(steps)) {
                const el = document.getElementById('node-' + id);
                const valEl = document.getElementById('val-' + id);
                if (el && valEl && run) {
                    const ms = run.mean * 1000;
                    const displayVal = ms < 1.0 
                        ? (run.mean * 1000000).toFixed(1) + ' μs' 
                        : ms.toFixed(2) + ' ms';
                    valEl.innerText = displayVal;

                    // Color grade boundary classes
                    el.className = 'brain-node';
                    if (ms < 1.0) el.classList.add('node-opt');
                    else if (ms < 15.0) el.classList.add('node-warn');
                    else el.classList.add('node-crit');
                }
            }
        }

        // Inspections inside map
        window.inspectNode = function(metricName) {
            const latest = {};
            runData.forEach(item => {
                latest[item.test_name] = item;
            });

            const run = latest[metricName];
            const panel = document.getElementById('inspectPanel');
            
            // Remove previous active outline
            document.querySelectorAll('.brain-node').forEach(node => node.classList.remove('active-inspect'));

            if (!run) return;

            // Highlight node
            const stepsMap = {
                'test_audio_normalizer_16bit_pcm_benchmark': 'audio',
                'test_hybrid_segmenter_benchmark': 'segmenter',
                'test_subconscious_threat_scan_benchmark': 'threat',
                'test_memory_semantic_retrieve_benchmark': 'memory',
                'test_endocrine_state_decay_benchmark': 'hormone',
                'test_personality_modulation_benchmark': 'modulate'
            };
            const nid = stepsMap[metricName];
            if (nid) {
                document.getElementById('node-' + nid).classList.add('active-inspect');
            }

            panel.style.display = 'block';
            document.getElementById('inspectName').innerText = niceNames[metricName] || metricName;
            
            const ms = run.mean * 1000;
            const meanDisplay = ms < 1.0 
                ? (run.mean * 1000000).toFixed(1) + ' μs' 
                : ms.toFixed(3) + ' ms';
            document.getElementById('inspectLatency').innerText = meanDisplay;

            document.getElementById('inspectOPS').innerText = run.ops.toLocaleString(undefined, {maximumFractionDigits: 0}) + ' OPS';
            
            const stdMs = run.stddev * 1000;
            const stdDisplay = stdMs < 1.0 
                ? (run.stddev * 1000000).toFixed(1) + ' μs' 
                : stdMs.toFixed(3) + ' ms';
            document.getElementById('inspectStdDev').innerText = stdDisplay;
        }

        // Category Tab Engine
        let chart = null;
        const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#14b8a6', '#f43f5e', '#a855f7'];

        window.switchPipeline = function(category, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const categoryTitles = {
                'telemetry': '⚡ Telemetry Loop Latency Trend',
                'cognitive': '🧠 Cognitive Brain State Latency Trend',
                'memory': '📁 Memory & NLP Search Latency Trend',
                'voice': '🗣️ Voice Core Latency Trend'
            };
            document.getElementById('chartTitle').innerText = categoryTitles[category];

            // Recompile category datasets
            const filteredRuns = runData.filter(item => pipelineMap[item.test_name] === category);
            
            // Build lines group by test
            const grouped = {};
            filteredRuns.forEach(item => {
                if (!grouped[item.test_name]) {
                    grouped[item.test_name] = {
                        label: niceNames[item.test_name] || item.test_name,
                        means: [],
                        runs: []
                    };
                }
                grouped[item.test_name].means.push((item.mean * 1000).toFixed(3));
                grouped[item.test_name].runs.push(`Run #${item.run_id}`);
            });

            const uniqueRuns = [...new Set(runData.map(item => `Run #${item.run_id}`))];
            const datasets = [];
            let colorIdx = 0;

            for (const [key, ds] of Object.entries(grouped)) {
                const color = colors[colorIdx % colors.length];
                colorIdx++;
                datasets.push({
                    label: ds.label,
                    data: ds.means,
                    borderColor: color,
                    backgroundColor: color + '15',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.2,
                    fill: true
                });
            }

            if (chart) chart.destroy();
            
            const ctx = document.getElementById('categoryChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: { labels: uniqueRuns, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#9ca3af', font: { family: 'Outfit', size: 11, weight: '500' } } }
                    },
                    scales: {
                        y: { 
                            grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
                            ticks: { color: '#9ca3af', font: { family: 'Outfit' } }, 
                            title: { display: true, text: 'Mean Latency (ms)', color: '#9ca3af', font: { family: 'Outfit', weight: '600' } } 
                        },
                        x: { 
                            grid: { display: false }, 
                            ticks: { color: '#9ca3af', font: { family: 'Outfit' } } 
                        }
                    }
                }
            });

            // Populate the right side panel sorted list of Throughput rankings
            populateRankingList(category);
        }

        // Horizontal bar rank list
        function populateRankingList(category) {
            const rankEl = document.getElementById('rankingList');
            rankEl.innerHTML = '';

            // Group by test name, take latest
            const latest = {};
            runData.forEach(item => {
                latest[item.test_name] = item;
            });

            const sorted = Object.values(latest)
                .filter(item => pipelineMap[item.test_name] === category)
                .sort((a, b) => b.ops - a.ops); // higher ops first (fastest first!)

            sorted.forEach(item => {
                const ms = item.mean * 1000;
                const timeText = ms < 1.0 
                    ? (item.mean * 1000000).toFixed(1) + ' μs' 
                    : ms.toFixed(3) + ' ms';
                
                const itemCard = document.createElement('div');
                itemCard.className = 'ranking-item';

                let badgeClass = 'badge-opt';
                if (ms >= 15.0) badgeClass = 'badge-crit';
                else if (ms >= 1.0) badgeClass = 'badge-warn';

                itemCard.innerHTML = `
                    <div class="ranking-meta">
                        <span class="ranking-name">${niceNames[item.test_name] || item.test_name}</span>
                        <span class="ranking-ops">${item.ops.toLocaleString(undefined, {maximumFractionDigits: 0})} OPS</span>
                    </div>
                    <span class="ranking-val ${badgeClass}">${timeText}</span>
                `;
                rankEl.appendChild(itemCard);
            });
        }

        // Populate Run Ledger rows
        function populateLedger() {
            const body = document.getElementById('tableBody');
            body.innerHTML = '';

            // Render in descending order (latest runs at top)
            const sortedDesc = [...runData].sort((a, b) => b.run_id - a.run_id);
            sortedDesc.forEach(item => {
                const row = document.createElement('tr');
                const ms = item.mean * 1000;
                const timeText = ms < 1.0 
                    ? (item.mean * 1000000).toFixed(1) + ' μs' 
                    : ms.toFixed(3) + ' ms';

                let badgeClass = 'badge-opt';
                if (ms >= 15.0) badgeClass = 'badge-crit';
                else if (ms >= 1.0) badgeClass = 'badge-warn';

                row.innerHTML = `
                    <td><strong>#${item.run_id}</strong></td>
                    <td>${item.timestamp.replace('T', ' ').split('.')[0]}</td>
                    <td style="color: var(--text-primary); font-weight: 600;">${niceNames[item.test_name] || item.test_name}</td>
                    <td>${(item.min * 1000).toFixed(3)} ms</td>
                    <td><span class="badge-kpi ${badgeClass}">${timeText}</span></td>
                    <td>${(item.max * 1000).toFixed(3)} ms</td>
                    <td>${(item.stddev * 1000).toFixed(3)} ms</td>
                    <td><span class="badge-kpi badge-opt">${item.ops.toLocaleString(undefined, {maximumFractionDigits: 0})} OPS</span></td>
                `;
                body.appendChild(row);
            });
        }

        // Bootstraps
        populateBrainMap();
        switchPipeline('telemetry', document.querySelector('.tab-btn'));
        populateLedger();
        
        // Auto inspect Node 1 on load
        inspectNode('test_audio_normalizer_16bit_pcm_benchmark');
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
