"""
AI Planner — Converts a user prompt into a multi-step AWS CLI execution plan.
Uses AWS Bedrock (Claude 3 Haiku) to generate ordered steps.

Output format:
    [
        {"step": 1, "action": "aws ec2 describe-vpn-connections"},
        {"step": 2, "action": "aws cloudwatch list-metrics --namespace AWS/VPN"}
    ]
"""

import json
import os

import boto3

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

_SYSTEM_PROMPT = """\
You are an AWS CLI expert and cloud operations engineer.
Convert the user request into an ordered execution plan of AWS CLI commands.

Output rules:
- Return ONLY a valid JSON array
- Each item: {"step": <number>, "action": "<aws cli command>"}
- Maximum 5 steps
- Only real, valid AWS CLI commands
- No explanation text outside the JSON
- No markdown, no code blocks
- Commands must be directly executable (no placeholders like <VPN_ID>)

Examples:

User: "cek VPN connection"
Output:
[
  {"step": 1, "action": "aws ec2 describe-vpn-connections"}
]

User: "kenapa VPN lambat"
Output:
[
  {"step": 1, "action": "aws ec2 describe-vpn-connections"},
  {"step": 2, "action": "aws cloudwatch list-metrics --namespace AWS/VPN"},
  {"step": 3, "action": "aws cloudwatch get-metric-statistics --namespace AWS/VPN --metric-name TunnelDataIn --period 3600 --statistics Average --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z"},
  {"step": 4, "action": "aws cloudwatch get-metric-statistics --namespace AWS/VPN --metric-name TunnelDataOut --period 3600 --statistics Average --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z"}
]"""


def create_plan(user_message: str) -> list[dict]:
    """
    Convert a natural language user message into an ordered AWS CLI execution plan.

    Args:
        user_message: Plain language request from the user.

    Returns:
        list[dict]: Ordered list of steps, each with "step" (int) and "action" (str).

    Raises:
        RuntimeError: If Bedrock invocation fails.
        ValueError:   If the model returns invalid JSON or wrong structure.
    """
    region  = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=region)
    client  = session.client("bedrock-runtime")

    prompt = f"{_SYSTEM_PROMPT}\n\nUser: {user_message}\nOutput:"

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

    # Strip markdown fences if model wraps output
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        steps = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {e}\nRaw: {raw_text}")

    if not isinstance(steps, list):
        raise ValueError(f"Expected a JSON array, got: {type(steps).__name__}")

    # Validate and normalize each step
    validated = []
    for i, item in enumerate(steps[:5], 1):
        if not isinstance(item, dict):
            continue
        action = item.get("action", "").strip()
        if not action.startswith("aws "):
            continue
        validated.append({"step": i, "action": action})

    if not validated:
        raise ValueError(f"No valid AWS CLI steps found in response: {steps}")

    return validated
