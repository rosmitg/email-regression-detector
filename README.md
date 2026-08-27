# Email Classifier Regression Detector

A CI/CD pipeline that catches LLM quality regressions
before they reach production.

## The Problem
AI teams ship prompt changes blind. Quality drops.
Users complain 3 days later. Nobody knows why.

## The Solution
Every prompt change automatically runs 50 labeled
test cases, scores quality with LLM-as-judge,
compares against baseline, and blocks deployment
if accuracy drops more than 8%.

## Architecture

prompts/v1.yaml (changed)
↓
GitHub Actions triggered
↓
50 test cases → classifier → scored
↓
Regression detected → Slack alert → PR blocked


## Stack
- Python 3.11
- OpenAI gpt-4o-mini (classifier + judge)
- Postgres on Neon (eval results)
- GitHub Actions (CI/CD)
- Slack webhooks (alerts)
- Docker

## Setup
```bash
cp .env.example .env
# fill in your keys
pip install -r requirements.txt
python -m src.database setup
```

## Results
- Caught X regressions during testing
- Prevented Y bad deploys
- Eval suite runs in ~60 seconds
