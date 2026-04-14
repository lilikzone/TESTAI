"""
Formatter Service — Orchestrates the output formatting step.
Uses Bedrock via ai_service for both format_result() and format_response().
"""

import re

from backend.services import ai_service

_MAX_INPUT_CHARS = 2000

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
    Summarize raw AWS CLI output using Bedrock.

    Input is truncated to 2000 characters before being sent to the model.

    Args:
        raw_output: Raw stdout string from an AWS CLI command.

    Returns:
        str: Plain-language summary covering status, issues, and recommendations.
    """
    if not raw_output or not raw_output.strip():
        return "No output returned from AWS CLI."

    truncated = raw_output.strip()[:_MAX_INPUT_CHARS]
    if len(raw_output.strip()) > _MAX_INPUT_CHARS:
        truncated += "\n... [output truncated]"

    prompt = _FORMAT_RESULT_PROMPT.format(raw_output=truncated)
    try:
        return ai_service._invoke(prompt, max_tokens=500)
    except Exception as e:
        raise RuntimeError(f"Bedrock failed to format the output: {str(e)}")


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
    Format raw AWS output into a human-readable summary.

    Args:
        raw_output:       stdout from cli_executor
        original_query:   the user's original natural language query
        executed_command: the AWS CLI command that was run

    Returns:
        str: Formatted, user-friendly summary with optional recommendations
    """
    if not raw_output or raw_output.strip() == "":
        return "The command executed successfully but returned no output."

    aws_service = _extract_service(executed_command)

    try:
        return ai_service.format_output(
            raw_output=raw_output,
            original_query=original_query,
            aws_service=aws_service,
        )
    except Exception as e:
        return f"[Formatter unavailable: {str(e)}]\n\nRaw output:\n{raw_output}"
