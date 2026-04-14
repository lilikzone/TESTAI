"""
Sanitizer — Strips sensitive fields from AWS CLI output before sending to AI.
Prevents secrets like PreSharedKey from being forwarded to Bedrock.
"""

import json

_MAX_OUTPUT_CHARS = 2000

_SENSITIVE_FIELDS = {"PreSharedKey", "CustomerGatewayConfiguration"}


def remove_sensitive_fields(data: dict | list) -> dict | list:
    """
    Recursively remove sensitive fields from a parsed JSON object or list.

    Traverses the entire structure and drops any key matching _SENSITIVE_FIELDS
    at any nesting level.

    Args:
        data: Parsed JSON — either a dict or a list.

    Returns:
        Cleaned dict or list with sensitive keys removed.

    Example:
        Input:  {"Tunnels": [{"OutsideIpAddress": "1.2.3.4", "PreSharedKey": "secret"}]}
        Output: {"Tunnels": [{"OutsideIpAddress": "1.2.3.4"}]}
    """
    if isinstance(data, dict):
        return {
            k: remove_sensitive_fields(v)
            for k, v in data.items()
            if k not in _SENSITIVE_FIELDS
        }
    if isinstance(data, list):
        return [remove_sensitive_fields(item) for item in data]
    return data


def sanitize_aws_output(raw_output: str) -> str:
    """
    Clean and truncate raw AWS CLI output before sending to AI formatter.

    Steps:
      1. Parse JSON safely — falls back to raw string if parsing fails
      2. Recursively remove sensitive fields (PreSharedKey, CustomerGatewayConfiguration)
      3. Re-serialize to compact JSON string
      4. Truncate to max 2000 characters

    Args:
        raw_output: Raw stdout string from AWS CLI execution.

    Returns:
        str: Sanitized string safe to send to AI models.
             - Valid JSON input  → cleaned compact JSON, max 2000 chars
             - Invalid JSON input → trimmed raw string, max 2000 chars
             - Empty input       → empty string
    """
    if not raw_output or not raw_output.strip():
        return ""

    try:
        parsed = json.loads(raw_output)
        cleaned = remove_sensitive_fields(parsed)
        result = json.dumps(cleaned, separators=(",", ":"))
    except json.JSONDecodeError:
        # Not JSON (plain text output) — use as-is
        result = raw_output.strip()

    if len(result) > _MAX_OUTPUT_CHARS:
        result = result[:_MAX_OUTPUT_CHARS] + "... [truncated]"

    return result
