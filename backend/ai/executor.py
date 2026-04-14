"""
AI Executor — Executes planned AWS CLI commands with approval gate for remediation.

Two modes:
  1. execute_plan(steps)
     — Runs read/describe commands immediately.
     — Returns {"steps": [...]} with results.

  2. execute_plan(steps, remediation_actions)
     — If remediation actions are present, does NOT execute them.
     — Returns {"needs_approval": True, "actions": [...]} for user review.

  3. execute_approved(actions)
     — Called only when user explicitly says "approve".
     — Validates each action against safe_commands before executing.
     — Attempts dry-run first if the command supports it.
"""

from backend.ai.safe_commands import is_blocked, is_safe
from backend.ai.audit import log_action
from backend.ai.rbac import check_permission
from backend.services.cli_executor import run_cli
from backend.services.sanitizer import sanitize_aws_output
from backend.utils.security import is_safe_command
import hashlib

# Shell injection characters that must never appear in any command
_FORBIDDEN_CHARS = [";", "&&", "|", "`", "$(", ">", "<"]

# EC2 commands that support --dry-run flag
# AWS only supports --dry-run on a specific subset of EC2 mutating operations
_DRY_RUN_SUPPORTED = {
    "aws ec2 start-instances",
    "aws ec2 stop-instances",
    "aws ec2 reboot-instances",
    "aws ec2 terminate-instances",
    "aws ec2 run-instances",
    "aws ec2 create-image",
    "aws ec2 create-snapshot",
    "aws ec2 create-volume",
    "aws ec2 attach-volume",
    "aws ec2 detach-volume",
    "aws ec2 associate-address",
    "aws ec2 disassociate-address",
    "aws ec2 create-tags",
    "aws ec2 delete-tags",
    "aws ec2 modify-instance-attribute",
}


def _supports_dry_run(command: str) -> bool:
    """Return True if the command supports AWS --dry-run flag."""
    return any(command.startswith(prefix) for prefix in _DRY_RUN_SUPPORTED)


def _dry_run(command: str) -> tuple[bool, str]:
    """
    Attempt a dry-run of the command by appending --dry-run.

    AWS dry-run returns exit code 255 with error code DryRunOperation
    if the user HAS permission (meaning the real call would succeed).
    Any other error means the real call would also fail.

    Returns:
        tuple[bool, str]: (would_succeed, message)
    """
    dry_command = f"{command} --dry-run"
    result = run_cli(dry_command)

    # DryRunOperation = permission check passed, real call would succeed
    if "DryRunOperation" in (result.get("error") or "") or \
       "DryRunOperation" in (result.get("output") or ""):
        return True, "Dry-run passed: permission check succeeded."

    # UnauthorizedOperation = no permission
    if "UnauthorizedOperation" in (result.get("error") or ""):
        return False, "Dry-run failed: insufficient IAM permissions for this action."

    # Other error — real execution would also fail
    error_msg = result.get("error") or result.get("output") or "Unknown dry-run error."
    return False, f"Dry-run failed: {error_msg[:200]}"


def is_valid_command(command: str) -> bool:
    """
    Check that a command contains no shell injection or chaining characters.

    Args:
        command: AWS CLI command string to validate.

    Returns:
        bool: True if command is clean, False if any forbidden pattern found.
    """
    forbidden = [";", "&&", "|"]
    return not any(f in command for f in forbidden)


def execute_plan(steps: list[dict], remediation_actions: list[dict] | None = None) -> dict:
    """
    Execute an ordered list of read/describe AWS CLI commands.

    If remediation_actions are provided, they are NOT executed — instead
    the function returns a pending approval response.

    Args:
        steps:               List of {"step", "action"} dicts from planner.
        remediation_actions: Optional list of {"description", "command", "risk"}
                             dicts from remediator. If present, triggers approval gate.

    Returns:
        dict — one of two shapes:

        Normal execution:
            {
                "steps": [
                    {"step": 1, "command": "...", "result": "...", "success": True}
                ]
            }

        Pending approval (when remediation_actions provided):
            {
                "needs_approval": True,
                "actions": [
                    {"description": "...", "command": "...", "risk": "low"}
                ]
            }
    """
    # Approval gate — return without executing if remediation is pending
    if remediation_actions:
        return {
            "needs_approval": True,
            "actions": remediation_actions,
        }

    executed = []

    for item in steps:
        step_num = item.get("step", len(executed) + 1)
        command  = item.get("action", "").strip()

        # Guard: skip non-AWS commands
        if not command.startswith("aws "):
            executed.append({
                "step":    step_num,
                "command": command,
                "result":  "Skipped: not a valid AWS CLI command.",
                "success": False,
            })
            continue

        # Guard: block destructive commands
        if not is_safe_command(command):
            executed.append({
                "step":    step_num,
                "command": command,
                "result":  "Blocked: command contains a destructive keyword.",
                "success": False,
            })
            continue

        raw = run_cli(command)
        result_text = sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"]

        log_action(
            user="system",
            command=command,
            result=result_text,
            status="success" if raw["success"] else "failed",
        )

        executed.append({
            "step":    step_num,
            "command": command,
            "result":  result_text,
            "success": raw["success"],
        })

    return {"steps": executed}


def execute_approved(actions: list[dict], user: str = "system", role: str = "operator") -> dict:
    """
    Execute remediation actions after explicit user approval.

    Validation layers (in order):
      1. Command must start with "aws "
      2. Command must pass is_valid_command() — no shell injection chars
      3. Command must pass is_safe() — must match safe command prefix list
      4. Command must not pass is_blocked() — no destructive keywords

    Args:
        actions: List of {"description", "command", "risk"} dicts,
                 typically from remediator.generate_remediation().

    Returns:
        dict:
            {
                "steps": [
                    {
                        "description": "...",
                        "command":     "...",
                        "risk":        "low",
                        "result":      "...",
                        "success":     True
                    }
                ]
            }
    """
    executed = []

    for action in actions:
        description = action.get("description", "")
        command     = action.get("command", "").strip()
        risk        = action.get("risk", "unknown")

        base = {"description": description, "command": command, "risk": risk,
                "action_id": action.get("action_id", ""), "hash": action.get("hash", "")}

        # Layer -1 — RBAC check
        allowed, reason = check_permission(role, action)
        if not allowed:
            msg = f"Rejected: {reason}"
            log_action(user=user, command=command, result=msg, status="rejected",
                       action_id=action.get("action_id", ""), hash=action.get("hash", ""))
            executed.append({**base, "result": msg, "success": False})
            continue

        # Layer 0 — verify hash matches command (tamper detection)
        expected_hash = action.get("hash", "")
        if expected_hash:
            actual_hash = hashlib.sha256(command.encode()).hexdigest()
            if actual_hash != expected_hash:
                msg = "Rejected: hash mismatch — command may have been tampered with."
                log_action(user=user, command=command, result=msg, status="rejected",
                           action_id=action.get("action_id", ""), hash=expected_hash)
                executed.append({**base, "result": msg, "success": False})
                continue

        # Layer 1 — must be an AWS CLI command
        if not command.startswith("aws "):
            executed.append({**base,
                "result": "Rejected: not a valid AWS CLI command.",
                "success": False})
            continue

        # Layer 2 — no shell injection or chaining characters
        if not is_valid_command(command):
            executed.append({**base,
                "result": "Rejected: command contains forbidden characters (;, &&, |).",
                "success": False})
            continue

        # Layer 3 — must match safe command prefix list
        if not is_safe(command):
            executed.append({**base,
                "result": "Rejected: command is not in the approved safe command list.",
                "success": False})
            continue

        # Layer 4 — must not contain destructive keywords
        if is_blocked(command):
            executed.append({**base,
                "result": "Rejected: command contains a blocked destructive keyword.",
                "success": False})
            continue

        # All checks passed — attempt dry-run if supported
        if _supports_dry_run(command):
            dry_ok, dry_msg = _dry_run(command)
            if not dry_ok:
                log_action(user=user, command=command, result=dry_msg, status="dry-run-failed",
                           action_id=action.get("action_id", ""), hash=action.get("hash", ""))
                executed.append({**base, "result": dry_msg, "success": False})
                continue

        # Real execution
        raw = run_cli(command)
        result_text = sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"]

        log_action(
            user=user,
            command=command,
            result=result_text,
            status="success" if raw["success"] else "failed",
            action_id=action.get("action_id", ""),
            hash=action.get("hash", ""),
        )

        executed.append({
            **base,
            "result":  result_text,
            "success": raw["success"],
        })

    return {"steps": executed}
