import os
import json
from datetime import datetime
from jinja2 import Template

REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Regression Report — {{ current_version }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            padding: 2rem;
        }
        .container { max-width: 1100px; margin: 0 auto; }

        .header {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }
        .header .subtitle {
            color: #888;
            font-size: 0.9rem;
        }

        .status-badge {
            display: inline-block;
            padding: 0.4rem 1rem;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            margin-top: 1rem;
        }
        .status-critical { background: #3d0000; color: #ff4444; border: 1px solid #ff4444; }
        .status-warning  { background: #2d1a00; color: #ffa500; border: 1px solid #ffa500; }
        .status-stable   { background: #002d00; color: #44ff44; border: 1px solid #44ff44; }
        .status-improved { background: #002d00; color: #44ff44; border: 1px solid #44ff44; }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
        }
        .metric-card .label {
            font-size: 0.8rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        }
        .metric-card .value {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }
        .metric-card .delta {
            font-size: 0.85rem;
        }
        .delta-positive { color: #44ff44; }
        .delta-negative { color: #ff4444; }
        .delta-neutral  { color: #888; }

        .section {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .section h2 {
            font-size: 1.1rem;
            margin-bottom: 1rem;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        th {
            text-align: left;
            padding: 0.75rem 1rem;
            color: #888;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #333;
        }
        td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #222;
            vertical-align: top;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #222; }

        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-pass     { background: #002d00; color: #44ff44; }
        .badge-fail     { background: #3d0000; color: #ff4444; }
        .badge-billing  { background: #1a1a3d; color: #6699ff; }
        .badge-technical{ background: #2d1a2d; color: #cc88ff; }
        .badge-account  { background: #1a2d1a; color: #88cc88; }
        .badge-general  { background: #2d2d1a; color: #cccc44; }
        .badge-easy     { background: #1a2d1a; color: #88cc88; }
        .badge-medium   { background: #2d2d1a; color: #cccc44; }
        .badge-hard     { background: #3d1a1a; color: #cc8888; }

        .regression-row td { background: #1a0000; }
        .improvement-row td { background: #001a00; }

        .email-preview {
            color: #888;
            font-size: 0.8rem;
            font-style: italic;
            margin-top: 0.3rem;
        }

        .footer {
            text-align: center;
            color: #555;
            font-size: 0.8rem;
            margin-top: 2rem;
        }
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>🔍 Regression Report</h1>
        <div class="subtitle">
            Generated {{ generated_at }} |
            Prompt: <strong>{{ previous_version }}</strong> →
            <strong>{{ current_version }}</strong>
        </div>
        <div class="status-badge status-{{ status }}">
            {{ status_emoji }} {{ status | upper }}
            {% if status == 'critical' %}— DEPLOYMENT BLOCKED{% endif %}
            {% if status == 'warning' %}— REVIEW REQUIRED{% endif %}
            {% if status == 'stable' %}— DEPLOYMENT APPROVED{% endif %}
            {% if status == 'improved' %}— DEPLOYMENT APPROVED{% endif %}
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="label">Accuracy</div>
            <div class="value">{{ accuracy_current }}%</div>
            <div class="delta {{ accuracy_delta_class }}">
                {{ accuracy_delta_str }} vs {{ accuracy_previous }}%
            </div>
        </div>
        <div class="metric-card">
            <div class="label">Regressions</div>
            <div class="value" style="color: {% if regression_count > 0 %}#ff4444{% else %}#44ff44{% endif %}">
                {{ regression_count }}
            </div>
            <div class="delta delta-neutral">cases broke</div>
        </div>
        <div class="metric-card">
            <div class="label">Latency</div>
            <div class="value">{{ latency_current }}s</div>
            <div class="delta {{ latency_delta_class }}">
                {{ latency_delta_str }} vs {{ latency_previous }}s
            </div>
        </div>
        <div class="metric-card">
            <div class="label">Cost</div>
            <div class="value">${{ cost_current }}</div>
            <div class="delta {{ cost_delta_class }}">
                {{ cost_delta_str }} vs ${{ cost_previous }}
            </div>
        </div>
    </div>

    {% if regressions %}
    <div class="section">
        <h2>❌ Regressions ({{ regressions | length }} cases broke)</h2>
        <table>
            <thead>
                <tr>
                    <th>Case ID</th>
                    <th>Expected</th>
                    <th>Previous</th>
                    <th>Now Getting</th>
                    <th>Difficulty</th>
                    <th>Email</th>
                </tr>
            </thead>
            <tbody>
                {% for r in regressions %}
                <tr class="regression-row">
                    <td><code>{{ r.case_id }}</code></td>
                    <td><span class="badge badge-{{ r.expected }}">{{ r.expected }}</span></td>
                    <td><span class="badge badge-{{ r.previous_got }}">{{ r.previous_got }}</span></td>
                    <td><span class="badge badge-{{ r.current_got }}">{{ r.current_got }}</span></td>
                    <td><span class="badge badge-{{ r.difficulty }}">{{ r.difficulty }}</span></td>
                    <td>
                        <div>{{ r.email_preview }}</div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if improvements %}
    <div class="section">
        <h2>✅ Improvements ({{ improvements | length }} cases fixed)</h2>
        <table>
            <thead>
                <tr>
                    <th>Case ID</th>
                    <th>Expected</th>
                    <th>Previous</th>
                    <th>Now Getting</th>
                </tr>
            </thead>
            <tbody>
                {% for i in improvements %}
                <tr class="improvement-row">
                    <td><code>{{ i.case_id }}</code></td>
                    <td><span class="badge badge-{{ i.expected }}">{{ i.expected }}</span></td>
                    <td><span class="badge badge-{{ i.previous_got }}">{{ i.previous_got }}</span></td>
                    <td><span class="badge badge-{{ i.current_got }}">{{ i.current_got }}</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <div class="section">
        <h2>📋 All Test Cases</h2>
        <table>
            <thead>
                <tr>
                    <th>Case ID</th>
                    <th>Result</th>
                    <th>Expected</th>
                    <th>Got</th>
                    <th>Difficulty</th>
                    <th>Judge</th>
                    <th>Latency</th>
                </tr>
            </thead>
            <tbody>
                {% for case in all_cases %}
                <tr>
                    <td><code>{{ case.case_id }}</code></td>
                    <td>
                        <span class="badge {% if case.passed %}badge-pass{% else %}badge-fail{% endif %}">
                            {% if case.passed %}✅ PASS{% else %}❌ FAIL{% endif %}
                        </span>
                    </td>
                    <td><span class="badge badge-{{ case.expected_category }}">{{ case.expected_category }}</span></td>
                    <td><span class="badge badge-{{ case.got_category }}">{{ case.got_category }}</span></td>
                    <td><span class="badge badge-{{ case.difficulty }}">{{ case.difficulty }}</span></td>
                    <td>{{ case.judge_score }}/5</td>
                    <td>{{ case.latency }}s</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Email Regression Detector — Built by Ross Gyawali
    </div>

</div>
</body>
</html>
"""

def delta_class(delta: float) -> str:
    if delta > 0:
        return "delta-positive"
    elif delta < 0:
        return "delta-negative"
    return "delta-neutral"

def delta_str(delta: float, prefix: str = "") -> str:
    if delta > 0:
        return f"+{delta}{prefix}"
    return f"{delta}{prefix}"

async def generate_html_report(
    comparison: dict,
    regressions: list,
    improvements: list,
    all_cases: list,
    output_path: str = "reports/latest.html"
) -> str:
    """Generate HTML diff report"""

    os.makedirs("reports", exist_ok=True)

    accuracy = comparison.get("accuracy", {})
    latency = comparison.get("latency", {})
    cost = comparison.get("cost", {})
    status = comparison.get("status", "stable")

    status_emojis = {
        "critical": "🚨",
        "warning": "⚠️",
        "stable": "✅",
        "improved": "✅"
    }

    acc_delta = accuracy.get("delta", 0)
    lat_delta = latency.get("delta", 0)
    cost_delta = cost.get("delta", 0)

    template = Template(REPORT_TEMPLATE)
    html = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        current_version=comparison.get("current_version", "v2"),
        previous_version=comparison.get("previous_version", "v1"),
        status=status,
        status_emoji=status_emojis.get(status, "❓"),
        accuracy_current=accuracy.get("current", 0),
        accuracy_previous=accuracy.get("previous", 0),
        accuracy_delta_str=f"{acc_delta:+.1f}%",
        accuracy_delta_class=delta_class(acc_delta),
        latency_current=latency.get("current", 0),
        latency_previous=latency.get("previous", 0),
        latency_delta_str=f"{lat_delta:+.3f}s",
        latency_delta_class=delta_class(-lat_delta),
        cost_current=f"{cost.get('current', 0):.4f}",
        cost_previous=f"{cost.get('previous', 0):.4f}",
        cost_delta_str=f"{cost_delta:+.6f}",
        cost_delta_class=delta_class(-cost_delta),
        regression_count=len(regressions),
        regressions=regressions,
        improvements=improvements,
        all_cases=all_cases
    )

    with open(output_path, "w") as f:
        f.write(html)

    print(f"📊 HTML report saved to {output_path}")
    return output_path