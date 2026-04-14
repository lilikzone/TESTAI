"""
Formatter Service — Summarizes AWS CLI output using AWS Bedrock.
"""

import json
import os
import re

import boto3

from backend.services import ai_service

_MAX_INPUT_CHARS = 2000
_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

_FORMAT_RESULT_PROMPT = (
    "You are a cloud engineer. Summarize AWS CLI output into simple explanation. "
    "Focus on:\n"
    "- status\n"
    "- issue\n"
    "- recommendation\n\n"
    "AWS CLI output:\n{raw_output}"
)


def format_result(raw_output: str) -> str:
    """
    Summarize raw AWS CLI output using AWS Bedrock (Claude 3 Haiku).

    Input is truncated to 2000 characters before being sent to the model
    to control token usage.

    Args:
        raw_output: Raw stdout string from an AWS CLI command.

    Returns:
        str: Plain-language summary covering status, issues, and recommendations.

    Raises:
        RuntimeError: If Bedrock invocation fails.
    """
    if not raw_output or not raw_output.strip():
        return "No output returned from AWS CLI."

    # Limit input to max 2000 characters
    truncated = raw_output.strip()[:_MAX_INPUT_CHARS]
    if len(raw_output.strip()) > _MAX_INPUT_CHARS:
        truncated += "\n... [output truncated]"

    prompt = _FORMAT_RESULT_PROMPT.format(raw_output=truncated)

    # Bedrock Claude models are available in us-east-1
    bedrock_region = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=bedrock_region)
    client = session.client("bedrock-runtime")

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
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

    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()


# --------------------------------------------------------------------------- #
# Pipeline helper — used by main.py full pipeline
# --------------------------------------------------------------------------- #

def _extract_service(command: str) -> str:
    """Extract AWS service name from a CLI command string."""
    match = re.match(r"aws\s+(\S+)", command)
    return match.group(1) if match else "aws"


def format_response(
    raw_output: str,
    original_query: str,
    executed_command: str,
) -> str:
    """
    Format raw AWS output into a human-readable summary (full pipeline variant).

    Args:
        raw_output:       stdout from cli_executor
        original_query:   the user's original natural language query
        executed_command: the AWS CLI command that was run

    Returns:
        str: Formatted, user-friendly summary with optional recommendations
    """
    if not raw_output or raw_output.strip() == "":
        return "The command executed successfully but returned no output."

    aws_service_name = _extract_service(executed_command)

    try:
        return ai_service.format_output(
            raw_output=raw_output,
            original_query=original_query,
            aws_service=aws_service_name,
        )
    except Exception as e:
        return f"[Formatter unavailable: {str(e)}]\n\nRaw output:\n{raw_output}"
