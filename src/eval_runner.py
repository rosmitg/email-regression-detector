import os
import json
import asyncio
import uuid
import anthropic
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import track

from src.classifier import classify_email
from src.database import (
    setup_database,
    save_eval_run,
    save_eval_result,
    update_run_summary,
    get_last_run,
    get_run_results
)

load_dotenv()

console = Console()


async def judge_summary(
    email: str,
    summary: str,
    category: str
) -> int:
    """LLM as judge - rates summary quality 1-5"""

    judge_client = anthropic.AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    prompt = f"""Rate the quality of this customer support email summary on a scale of 1-5.

Email: {email}
Category: {category}
Summary: {summary}

Scoring criteria:
5 - Perfect: accurate, concise, captures the key issue
4 - Good: accurate, mostly concise, captures the issue
3 - Okay: accurate but too vague or too verbose
2 - Poor: partially inaccurate or misses the main issue
1 - Bad: inaccurate or completely misses the issue

Respond with ONLY a single number (1, 2, 3, 4, or 5). Nothing else."""

    response = await judge_client.messages.create(
        model=os.getenv("JUDGE_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        score = int(response.content[0].text.strip())
        return max(1, min(5, score))
    except:
        return 3


def load_golden_dataset() -> list:
    """Load the golden dataset from JSON"""
    with open("data/golden_dataset.json", "r") as f:
        data = json.load(f)
    return data["cases"]


async def run_single_case(
    case: dict,
    prompt_version: str,
    run_id: str
) -> dict:
    """Run a single test case through the classifier"""

    result = await classify_email(
        case["email"],
        prompt_version
    )

    passed = result["category"] == case["expected_category"]

    judge_score = await judge_summary(
        case["email"],
        result["summary"],
        result["category"]
    )

    full_result = {
        "case_id": case["id"],
        "run_id": run_id,
        "prompt_version": prompt_version,
        "email_text": case["email"],
        "expected_category": case["expected_category"],
        "got_category": result["category"],
        "summary": result["summary"],
        "confidence": result["confidence"],
        "judge_score": judge_score,
        "passed": passed,
        "latency": result["latency"],
        "cost": result["cost"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "difficulty": case.get("difficulty", "medium")
    }

    await save_eval_result(run_id, full_result)
    return full_result


async def run_eval(prompt_version: str = "v1") -> dict:
    """
    Main eval runner
    Runs all 50 test cases and returns summary metrics
    """
    await setup_database()

    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    console.print(f"\n[bold blue]Starting eval run: {run_id}[/bold blue]")
    console.print(f"Prompt version: [yellow]{prompt_version}[/yellow]")

    await save_eval_run(run_id, prompt_version)

    cases = load_golden_dataset()
    console.print(f"Running [green]{len(cases)}[/green] test cases...\n")

    results = []
    for case in track(cases, description="Running evals..."):
        result = await run_single_case(case, prompt_version, run_id)
        results.append(result)
        await asyncio.sleep(0.1)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    accuracy = passed / len(results)
    avg_latency = sum(r["latency"] for r in results) / len(results)
    avg_cost = sum(r["cost"] for r in results) / len(results)
    total_cost = sum(r["cost"] for r in results)
    avg_judge = sum(r["judge_score"] for r in results) / len(results)

    summary = {
        "run_id": run_id,
        "prompt_version": prompt_version,
        "total_cases": len(results),
        "passed": passed,
        "failed": failed,
        "accuracy": accuracy,
        "avg_latency": round(avg_latency, 3),
        "avg_cost": round(avg_cost, 6),
        "total_cost": round(total_cost, 6),
        "avg_judge_score": round(avg_judge, 2),
        "failed_cases": [
            {
                "case_id": r["case_id"],
                "expected": r["expected_category"],
                "got": r["got_category"],
                "difficulty": r["difficulty"]
            }
            for r in results if not r["passed"]
        ]
    }

    await update_run_summary(run_id, summary)
    print_results_table(summary)

    # Run regression detection
    from src.regression import (
        compare_runs,
        find_regressions,
        format_regression_report
    )

    previous = await get_last_run(current_run_id=run_id)

    if previous and previous["run_id"] != run_id:
        comparison = compare_runs(summary, dict(previous))
        regressions, improvements = await find_regressions(
            run_id, previous["run_id"]
        )
        report = format_regression_report(
            comparison, regressions, improvements
        )
        console.print(f"\n[bold yellow]{'='*50}[/bold yellow]")
        console.print(report)
        console.print(f"[bold yellow]{'='*50}[/bold yellow]\n")
        summary["regression_report"] = report
        summary["regressions"] = regressions
        summary["comparison"] = comparison

    return summary


def print_results_table(summary: dict):
    """Print a beautiful results table"""

    console.print(f"\n[bold green]Eval Complete[/bold green]")

    table = Table(title=f"Eval Results — {summary['prompt_version']}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    if summary["accuracy"] >= 0.90:
        status = "✅ PASS"
    elif summary["accuracy"] >= 0.85:
        status = "⚠️  WARN"
    else:
        status = "❌ FAIL"

    table.add_row("Status", status)
    table.add_row("Accuracy", f"{summary['accuracy']*100:.1f}%")
    table.add_row("Passed", str(summary["passed"]))
    table.add_row("Failed", str(summary["failed"]))
    table.add_row("Avg Latency", f"{summary['avg_latency']}s")
    table.add_row("Total Cost", f"${summary['total_cost']:.4f}")
    table.add_row("Avg Judge Score", f"{summary['avg_judge_score']}/5")

    console.print(table)

    if summary["failed_cases"]:
        console.print("\n[bold red]Failed Cases:[/bold red]")
        fail_table = Table()
        fail_table.add_column("Case ID", style="cyan")
        fail_table.add_column("Expected", style="green")
        fail_table.add_column("Got", style="red")
        fail_table.add_column("Difficulty", style="yellow")

        for case in summary["failed_cases"]:
            fail_table.add_row(
                case["case_id"],
                case["expected"],
                case["got"],
                case["difficulty"]
            )

        console.print(fail_table)


if __name__ == "__main__":
    import sys
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    asyncio.run(run_eval(version))