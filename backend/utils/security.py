"""
Security utility — Guardrail validation before AWS execution.
Classifies risk level and blocks dangerous commands.
"""

import re
from dataclasses import dataclass

# Commands that are always blocked, no exceptions
BLOCKED_KEYWORDS = ["delete", "terminate", "remove", "shutdown"]

HARD_BLOCKLIST = [
    r"iam\s+delete-account",
    r"organizations\s+delete-organization",
    r"organizations\s+remove-account",
    r"iam\s+attach-user-policy.+AdministratorAccess",
    r"ec2\s+terminate-instances\s+--instance-ids\s+\$\(",  # subshell wildcard
    r"s3\s+rb\s+--force",
    r"s3\s+rm\s+s3://\s+--recursive",  # root recursive delete
]

DESTRUCTIVE_PATTERNS = [
    r"\bterminate\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\bpurge\b",
    r"\bdrop\b",
    r"\bdestroy\b",
]

MODIFY_PATTERNS = [
    r"\bcreate\b",
    r"\bupdate\b",
    r"\bput\b",
    r"\bstart\b",
    r"\bstop\b",
    r"\breboot\b",
    r"\bmodify\b",
    r"\battach\b",
    r"\bdetach\b",
]


@dataclass
class ValidationResult:
    allowed: bool
    risk_level: str  # READ_ONLY | MODIFY | DESTRUCTIVE | BLOCKED
    reason: str | None
    requires_confirmation: bool


def is_safe_command(command: str) -> bool:
    """
    Check whether a command is safe to execute.

    Performs a case-insensitive scan for blocked keywords.
    Returns False immediately if any blocked keyword is found.

    Args:
        command: AWS CLI command string to evaluate.

    Returns:
        bool: True if no blocked keywords are found, False otherwise.
    """
    cmd_lower = command.lower()
    return not any(keyword in cmd_lower for keyword in BLOCKED_KEYWORDS)


def validate(command: str) -> ValidationResult:
    """Validate an AWS CLI command before execution."""
    cmd_lower = command.lower()

    # Check hard blocklist first
    for pattern in HARD_BLOCKLIST:
        if re.search(pattern, cmd_lower):
            return ValidationResult(
                allowed=False,
                risk_level="BLOCKED",
                reason=f"Command matches hard blocklist pattern: '{pattern}'. This operation is permanently restricted.",
                requires_confirmation=False,
            )

    # Check destructive patterns
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, cmd_lower):
            return ValidationResult(
                allowed=False,
                risk_level="DESTRUCTIVE",
                reason="Command contains a destructive operation. Explicit confirmation required before execution.",
                requires_confirmation=True,
            )

    # Check modify patterns
    for pattern in MODIFY_PATTERNS:
        if re.search(pattern, cmd_lower):
            return ValidationResult(
                allowed=True,
                risk_level="MODIFY",
                reason=None,
                requires_confirmation=False,
            )

    # Default: read-only
    return ValidationResult(
        allowed=True,
        risk_level="READ_ONLY",
        reason=None,
        requires_confirmation=False,
    )
