"""
Planner Service — Breaks down a user request into ordered AWS CLI steps.
Uses AWS Bedrock (Claude 3 Haiku) to generate a structured action plan.
"""

import json
import os

import boto3

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

_SYSTEM_PROMPT = """\
You are an AWS cloud engineer.
Break down the user request into steps.
Return JSON:
{
  "steps": [
    { "description": "...", "command": "aws ..." }
  ]
}
Rules:
- Max 5 steps
- Each step must contain a valid, real AWS CLI command that exists
- Only use well-known AWS CLI commands (describe-*, list-*, get-*)
- Do NOT invent commands — if unsure, reuse describe-* commands with different --query filters
- Be relevant to user request
- Do NOT explain outside JSON
- Return ONLY the JSON object, no markdown, no code block"""


def plan_actions(user_input: str) -> dict:
    """
    Break down a natural language request into ordered AWS CLI steps.

    Args:
        user_input: Plain language description of what the user wants to do.

    Returns:
        dict: Parsed JSON with key "steps", each containing
              "description" and "command".

    Raises:
        RuntimeError: If Bedrock invocation fails.
        ValueError:   If the model returns invalid or non-JSON output.
    """
    region  = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=region)
    client  = session.client("bedrock-runtime")

    prompt = f"{_SYSTEM_PROMPT}\n\nUser request: {user_input}"

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    })

    try:
        response = client.invoke_model(
            modelId=_BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
    except Exception as e:
        raise RuntimeError(f"Bedrock invocation failed: {str(e)}")

    raw_text = json.loads(response["body"].read())["content"][0]["text"].strip()

    # Strip markdown fences if model wraps output anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {e}\nRaw: {raw_text}")

    if "steps" not in result:
        raise ValueError(f"Missing 'steps' key in response: {result}")

    # Enforce max 5 steps
    result["steps"] = result["steps"][:5]

    return result
