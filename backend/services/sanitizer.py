"""
Sanitizer — Strips sensitive fields from AWS CLI output before sending to AI.
Prevents secrets like PreSharedKey from being sent to Bedrock.
"""

import json

_MAX_OUTPUT_CHARS = 4000

# Fields to remove recursively from any nested JSON structure
_SENSITIVE_FIELDS = {"PreSharedKey", "CustomerGatewayConfiguration"}


def _remove_sensitive(obj: any) -> any:
    """Recursively remove sensitive fields from a parsed JSON object."""
    if isinstance(obj, dict):
        return {
            k: _remove_sensitive(v)
            for k, v in obj.items()
            if k not in _SENSITIVE_FIELDS
        }
    if isinstance(obj, list):
        return [_remove_sensitive(item) for item in obj]
    return obj


def sanitize_aws_output(raw_json: str) -> str:
    """
    Remove sensitive fields from AWS CLI JSON output and truncate to 2000 chars.

    Steps:
      1. Parse JSON (falls back to raw string if not valid JSON)
      2. Recursively remove PreSharedKey and CustomerGatewayConfiguration
      3. Re-serialize to compact JSON string
      4. Truncate to max 2000 characters

    Args:
        raw_json: Raw stdout string from AWS CLI execution.

    Returns:
        str: Sanitized JSON string, safe to send to AI models.
    """
    if not raw_json or not raw_json.strip():
        return ""

    # Try to parse and clean as JSON
    try:
        parsed = json.loads(raw_json)
        cleaned = _remove_sensitive(parsed)
        result = json.dumps(cleaned, separators=(",", ":"))
    except json.JSONDecodeError:
        # Not JSON (e.g. plain text output) — use as-is
        result = raw_json.strip()

    # Truncate to max 2000 characters
    if len(result) > _MAX_OUTPUT_CHARS:
        result = result[:_MAX_OUTPUT_CHARS] + "... [truncated]"

    return result
