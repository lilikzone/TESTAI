"""
Formatter Service — Orchestrates the output formatting step.
Wraps ai_service.format_output() with error handling and
extracts the AWS service name from the executed command.
"""

import re

from backend.services import ai_service


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
        # Fallback: return raw output if Gemini fails
        return f"[Formatter unavailable: {str(e)}]\n\nRaw output:\n{raw_output}"
