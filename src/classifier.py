import os
import json
import yaml
import time
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    response = await client.chat.completions.create(
        model=os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": prompt_config["system_prompt"]
            },
            {
                "role": "user",
                "content": f"Classify this email:\n\n{email_text}"
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    latency = time.time() - start_time
    raw_output = response.choices[0].message.content
    parsed = json.loads(raw_output)

    return {
        "category": parsed.get("category", "general"),
        "summary": parsed.get("summary", ""),
        "confidence": parsed.get("confidence", 0.5),
        "latency": round(latency, 3),
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "cost": calculate_cost(
            response.usage.prompt_tokens,
            response.usage.completion_tokens
        ),
        "prompt_version": prompt_version,
        "raw_output": raw_output
    }

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for gpt-4o-mini"""
    input_cost = (input_tokens / 1_000_000) * 0.15
    output_cost = (output_tokens / 1_000_000) * 0.60
    return round(input_cost + output_cost, 6)