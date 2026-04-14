"""
Audit Logger — Records every executed AWS CLI action for compliance and traceability.

Storage: append-only JSONL file (one JSON object per line).
Location: logs/audit.jsonl (configurable via AUDIT_LOG_PATH env var)
Fallback: stdout if file cannot be written.

Each entry:
    {
        "timestamp":  "2026-04-15T10:00:00Z",
        "user":       "lilikzone",
        "command":    "aws ec2 describe-vpn-connections",
        "status":     "success",
        "action_id":  "uuid or empty",
        "hash":       "sha256 or empty",
        "detail":     "optional result summary or error"
    }
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_LOG_PATH = Path("logs/audit.jsonl")


def _get_log_path() -> Path:
    return Path(os.getenv("AUDIT_LOG_PATH", str(_DEFAULT_LOG_PATH)))


def _ensure_log_dir(path: Path) -> bool:
    """Create parent directory if needed. Returns True if writable."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def log_action(
    user:      str,
    command:   str,
    result:    str,
    status:    str = "success",
    action_id: str = "",
    hash:      str = "",
) -> dict:
    """
    Record an executed AWS CLI action to the audit log.

    Args:
        user:      Identity of the user or system that triggered the action.
        command:   The AWS CLI command that was executed.
        result:    Output or error message from execution.
        status:    "success", "failed", "blocked", or "rejected".
        action_id: Optional UUID from remediator (for approved actions).
        hash:      Optional SHA256 hash of the command (for approved actions).

    Returns:
        dict: The audit entry that was written.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user":      user,
        "command":   command,
        "status":    status,
        "action_id": action_id,
        "hash":      hash,
        "detail":    result[:500] if result else "",
    }

    log_path = _get_log_path()

    if _ensure_log_dir(log_path):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            # Fallback to stdout if file write fails
            print(f"[AUDIT] {json.dumps(entry)} (file write failed: {e})")
    else:
        print(f"[AUDIT] {json.dumps(entry)}")

    return entry


def get_recent_logs(n: int = 50) -> list[dict]:
    """
    Read the last N audit log entries.

    Args:
        n: Number of most recent entries to return (default 50).

    Returns:
        list[dict]: Parsed log entries, most recent last.
    """
    log_path = _get_log_path()

    if not log_path.exists():
        return []

    try:
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries[-n:]
    except OSError:
        return []
