import os
from dotenv import load_dotenv
from src.database import get_last_run, get_run_results

load_dotenv()

# Thresholds
WARN_THRESHOLD = 0.03   # 3% drop = warning
CRITICAL_THRESHOLD = 0.08  # 8% drop = critical block

def compare_runs(current: dict, previous: dict) -> dict:
    """
    Compare current eval run against previous baseline
    Returns regression report
    """
    if not previous:
        return {
            "has_previous": False,
            "status": "baseline",
            "message": "First run — establishing baseline"
        }

    accuracy_delta = current["accuracy"] - previous["accuracy"]
    latency_delta = current["avg_latency"] - previous["avg_latency"]
    cost_delta = current["total_cost"] - previous["total_cost"]
    judge_delta = current.get("avg_judge_score", 0) - previous.get("avg_judge_score", 0)

    if accuracy_delta <= -CRITICAL_THRESHOLD:
        status = "critical"
    elif accuracy_delta <= -WARN_THRESHOLD:
        status = "warning"
    elif accuracy_delta > 0:
        status = "improved"
    else:
        status = "stable"

    return {
        "has_previous": True,
        "status": status,
        "current_version": current["prompt_version"],
        "previous_version": previous["prompt_version"],
        "accuracy": {
            "current": round(current["accuracy"] * 100, 1),
            "previous": round(previous["accuracy"] * 100, 1),
            "delta": round(accuracy_delta * 100, 1)
        },
        "latency": {
            "current": current["avg_latency"],
            "previous": previous["avg_latency"],
            "delta": round(latency_delta, 3)
        },
        "cost": {
            "current": current["total_cost"],
            "previous": previous["total_cost"],
            "delta": round(cost_delta, 6)
        },
        "judge_score": {
            "current": current.get("avg_judge_score", 0),
            "previous": previous.get("avg_judge_score", 0),
            "delta": round(judge_delta, 2)
        }
    }

async def find_regressions(
    current_run_id: str,
    previous_run_id: str
) -> list:
    """
    Find specific test cases that regressed
    Passed before but fail now
    """
    current_results = await get_run_results(current_run_id)
    previous_results = await get_run_results(previous_run_id)

    previous_map = {r["case_id"]: r for r in previous_results}

    regressions = []
    improvements = []

    for result in current_results:
        case_id = result["case_id"]
        prev = previous_map.get(case_id)

        if not prev:
            continue

        was_passing = prev["passed"]
        now_passing = result["passed"]

        if was_passing and not now_passing:
            regressions.append({
                "case_id": case_id,
                "expected": result["expected_category"],
                "previous_got": prev["got_category"],
                "current_got": result["got_category"],
                "difficulty": result.get("difficulty", "medium"),
                "email_preview": result["email_text"][:80] + "..."
            })

        elif not was_passing and now_passing:
            improvements.append({
                "case_id": case_id,
                "expected": result["expected_category"],
                "previous_got": prev["got_category"],
                "current_got": result["got_category"],
            })

    return regressions, improvements

def format_regression_report(
    comparison: dict,
    regressions: list,
    improvements: list
) -> str:
    """Format a human readable regression report"""

    status_emoji = {
        "critical": "🚨",
        "warning": "⚠️",
        "improved": "✅",
        "stable": "✅",
        "baseline": "📊"
    }

    emoji = status_emoji.get(comparison["status"], "❓")
    status = comparison["status"].upper()

    lines = [
        f"{emoji} REGRESSION REPORT — {status}",
        f"",
        f"Prompt: {comparison.get('previous_version', 'N/A')} → {comparison.get('current_version', 'N/A')}",
        f"",
        f"METRICS:",
        f"  Accuracy:    {comparison['accuracy']['previous']}% → {comparison['accuracy']['current']}% ({comparison['accuracy']['delta']:+.1f}%)",
        f"  Latency:     {comparison['latency']['previous']}s → {comparison['latency']['current']}s ({comparison['latency']['delta']:+.3f}s)",
        f"  Cost:        ${comparison['cost']['previous']:.4f} → ${comparison['cost']['current']:.4f} ({comparison['cost']['delta']:+.6f})",
        f"  Judge Score: {comparison['judge_score']['previous']}/5 → {comparison['judge_score']['current']}/5 ({comparison['judge_score']['delta']:+.2f})",
    ]

    if regressions:
        lines.append(f"\nREGRESSIONS ({len(regressions)} cases broke):")
        for r in regressions:
            lines.append(
                f"  ❌ {r['case_id']} [{r['difficulty']}]: "
                f"expected '{r['expected']}' "
                f"prev got '{r['previous_got']}' "
                f"now got '{r['current_got']}'"
            )
            lines.append(f"     Email: {r['email_preview']}")

    if improvements:
        lines.append(f"\nIMPROVEMENTS ({len(improvements)} cases fixed):")
        for i in improvements:
            lines.append(
                f"  ✅ {i['case_id']}: "
                f"expected '{i['expected']}' "
                f"now correctly got '{i['current_got']}'"
            )

    if comparison["status"] == "critical":
        lines.append(f"\n🚨 DEPLOYMENT BLOCKED")
        lines.append(f"Accuracy dropped {abs(comparison['accuracy']['delta'])}% — exceeds {CRITICAL_THRESHOLD*100}% threshold")
    elif comparison["status"] == "warning":
        lines.append(f"\n⚠️  WARNING — Review required")
        lines.append(f"Accuracy dropped {abs(comparison['accuracy']['delta'])}%")

    return "\n".join(lines)