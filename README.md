# Email Classifier Regression Detector

A CI/CD pipeline that automatically catches LLM quality regressions
before they reach production.

## The Problem

AI teams change prompts constantly. Quality drops silently.
Users complain 3 days later. Nobody knows what changed or why.

## The Solution

Every prompt change automatically:

1. Runs 50 hand-labeled test cases through the classifier
2. Scores outputs with LLM-as-judge
3. Compares against the previous baseline
4. Detects regressions (cases that passed before but fail now)
5. Sends a Slack alert with summary and top failures
6. Generates a full HTML diff report
7. Blocks deployment if accuracy drops more than 8%

## Results

- v1 baseline: 94% accuracy, 4.88/5 judge score, $0.0178 total cost
- v2 degraded: 90% accuracy, 1 regression detected (case_040)
- Eval suite runs in ~3 minutes for 50 cases
- Total cost per eval run: ~$0.016

## Architecture

    prompts/v1.yaml changed to v2.yaml
            |
    GitHub Actions triggered on push
            |
    50 test cases sent to Claude Haiku
            |
    LLM-as-judge scores each summary (1-5)
            |
    Regression detection compares v2 vs v1
            |
    Slack alert fires with summary
            |
    HTML diff report generated
            |
    PR blocked if accuracy drops more than 8%

## Tech Stack

| Component      | Tool                  |
|----------------|-----------------------|
| LLM            | Claude Haiku          |
| Eval framework | Custom + LLM-as-judge |
| Database       | PostgreSQL on Neon    |
| Alerting       | Slack Webhooks        |
| CI/CD          | GitHub Actions        |
| Reporting      | Custom HTML           |
| Language       | Python 3.11           |

## Setup

```bash
git clone https://github.com/rosmitg/email-regression-detector
cd email-regression-detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in your keys in .env then run:

```bash
python -c "import asyncio; from src.database import setup_database; asyncio.run(setup_database())"
python -m src.eval_runner v1
python -m src.eval_runner v2
```

## GitHub Actions Setup

Add these secrets to your repo under Settings > Secrets:

- ANTHROPIC_API_KEY
- DATABASE_URL
- SLACK_WEBHOOK_URL

CI triggers automatically on any change to the prompts/ directory.

## Project Structure

    email-regression-detector/
    ├── prompts/
    │   ├── v1.yaml              baseline prompt (94% accuracy)
    │   └── v2.yaml              degraded prompt (90% accuracy)
    ├── data/
    │   └── golden_dataset.json  50 hand-labeled test cases
    ├── src/
    │   ├── classifier.py        Claude Haiku email classifier
    │   ├── eval_runner.py       runs all test cases + regression detection
    │   ├── regression.py        compares runs, finds regressions
    │   ├── alerts.py            Slack webhook integration
    │   ├── report.py            HTML diff report generator
    │   └── database.py          PostgreSQL connection and queries
    ├── .github/
    │   └── workflows/
    │       └── eval.yml         GitHub Actions CI/CD
    ├── requirements.txt
    ├── Dockerfile
    └── .env.example

## Why Not Just Use LangSmith?

LangSmith is an observability tool — it shows you what happened after the fact.
This system is a quality gate — it prevents bad deploys before they happen.

- LangSmith = security camera (records everything)
- This system = burglar alarm (stops problems before users see them)

## Interview Talking Points

- Golden dataset of 50 hand-labeled cases (not AI generated)
- LLM-as-judge scores summary quality independently from category accuracy
- Regression detection compares specific cases not just aggregate metrics
- Statistical thresholds: 3% drop = warning, 8% drop = critical and blocked
- GitHub Actions triggers on prompt file changes only
- Slack alert shows summary plus top failures plus link to full HTML report

## Next Steps

- Host HTML reports on S3 with pre-signed URLs in Slack alerts
- Add per-category accuracy breakdown
- Integrate with LangSmith for full observability stack
- Add semantic similarity scoring for edge cases
