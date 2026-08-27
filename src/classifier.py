import os
import json
import yaml
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def load_prompt(version: str) -> dict:
    """Load prompt from versioned YAML file"""
    path = f"prompts/{version}.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)

async def classify_email(
    email_text: str,
    prompt_version: str = "v1"
) -> dict:
    """
    Classify a customer support email
    Returns category, summary, confidence, latency, tokens, cost
    """
    prompt_config = load_prompt(prompt_version)

    start_time = time.time()

    response = await client.messages.create(
        model=os.getenv("CLASSIFIER_MODEL", "claude-haiku-3-5-20251001"),
        max_tokens=200,
        system=prompt_config["system_prompt"],
        messages=[
            {
                "role": "user",
                "content": f"Classify this email:\n\n{email_text}"
            }
        ]
    )

    latency = time.time() - start_time
    raw_output = response.content[0].text

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {
                "category": "general",
                "summary": "Could not parse response",
                "confidence": 0.0
            }

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    return {
        "category": parsed.get("category", "general"),
        "summary": parsed.get("summary", ""),
        "confidence": parsed.get("confidence", 0.5),
        "latency": round(latency, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": calculate_cost(input_tokens, output_tokens),
        "prompt_version": prompt_version,
        "raw_output": raw_output
    }

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for claude-haiku"""
    input_cost = (input_tokens / 1_000_000) * 0.80
    output_cost = (output_tokens / 1_000_000) * 4.00
    return round(input_cost + output_cost, 6)