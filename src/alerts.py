import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def get_most_affected_category(regressions: list) -> str:
    """Find which category regressed most"""
    if not regressions:
        return "none"
    
    categories = {}
    for r in regressions:
        cat = r["expected"]
        categories[cat] = categories.get(cat, 0) + 1
    
    return max(categories, key=categories.get)

async def send_slack_alert(
    comparison: dict,
    regressions: list,
    improvements: list
) -> bool:
    """Send regression alert to Slack"""

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("No Slack webhook configured - skipping alert")
        return False

    status = comparison.get("status", "unknown")

    status_config = {
        "critical": {"emoji": "🚨", "color": "#FF0000", "label": "CRITICAL"},
        "warning":  {"emoji": "⚠️",  "color": "#FFA500", "label": "WARNING"},
        "improved": {"emoji": "✅", "color": "#00FF00", "label": "IMPROVED"},
        "stable":   {"emoji": "✅", "color": "#36a64f", "label": "STABLE"},
    }

    config = status_config.get(status, {
        "emoji": "❓",
        "color": "#808080",
        "label": "UNKNOWN"
    })

    accuracy = comparison.get("accuracy", {})
    latency = comparison.get("latency", {})
    cost = comparison.get("cost", {})
    judge = comparison.get("judge_score", {})

    acc_delta = accuracy.get('delta', 0)
    acc_current = accuracy.get('current', 0)
    acc_previous = accuracy.get('previous', 0)

    most_affected = get_most_affected_category(regressions)

    # Determine deployment decision
    if status == "critical":
        deployment_text = "🚨 *DEPLOYMENT BLOCKED*"
    elif status == "warning":
        deployment_text = "⚠️ *DEPLOYMENT FLAGGED — Review required*"
    elif status == "improved":
        deployment_text = "✅ *DEPLOYMENT APPROVED — Quality improved*"
    else:
        deployment_text = "✅ *DEPLOYMENT APPROVED — Quality stable*"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{config['emoji']} LLM Regression Report — {config['label']}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Prompt:* `{comparison.get('previous_version')}` → "
                    f"`{comparison.get('current_version')}`\n"
                    f"*Decision:* {deployment_text}"
                )
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*📊 Accuracy*\n"
                        f"{acc_previous}% → {acc_current}% "
                        f"({acc_delta:+.1f}%)"
                    )
                },
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*⏱️ Latency*\n"
                        f"{latency.get('previous')}s → "
                        f"{latency.get('current')}s "
                        f"({latency.get('delta', 0):+.3f}s)"
                    )
                },
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*💰 Cost*\n"
                        f"${cost.get('previous'):.4f} → "
                        f"${cost.get('current'):.4f} "
                        f"({cost.get('delta', 0):+.6f})"
                    )
                },
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*⭐ Judge Score*\n"
                        f"{judge.get('previous', 0)}/5 → "
                        f"{judge.get('current', 0)}/5 "
                        f"({judge.get('delta', 0):+.2f})"
                    )
                }
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*❌ Regressions:* {len(regressions)} cases broke"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*✅ Improvements:* {len(improvements)} cases fixed"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*🎯 Top failure:* `{most_affected}` category hit hardest"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*📋 Test cases:* 50 total"
                }
            ]
        }
    ]

    # Add top 3 regressions as context
    if regressions:
        top3 = regressions[:3]
        context_text = "*Top regressions:*\n"
        for r in top3:
            context_text += (
                f"• `{r['case_id']}` — "
                f"expected `{r['expected']}` "
                f"got `{r['current_got']}` "
                f"[{r['difficulty']}]\n"
            )

        if len(regressions) > 3:
            context_text += f"_...and {len(regressions) - 3} more_\n"

        context_text += f"\n<https://github.com/rosmitg/email-regression-detector/actions|View full report on GitHub Actions>"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": context_text
            }
        })

    payload = {
        "attachments": [
            {
                "color": config["color"],
                "blocks": blocks
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            webhook_url,
            json=payload,
            timeout=10.0
        )

    if response.status_code == 200:
        print("✅ Slack alert sent successfully")
        return True
    else:
        print(f"❌ Slack alert failed: {response.status_code} {response.text}")
        return False