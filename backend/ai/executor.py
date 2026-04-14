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
"""

from backend.ai.safe_commands import is_blocked, is_safe
from backend.services.cli_executor import run_cli
from backend.services.sanitizer import sanitize_aws_output
from backend.utils.security import is_safe_command

# Shell injection characters that must never appear in any command
_FORBIDDEN_CHARS = [";", "&&", "|", "`", "$(", ">", "<"]


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

        executed.append({
            "step":    step_num,
            "command": command,
            "result":  sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"],
            "success": raw["success"],
        })

    return {"steps": executed}


def execute_approved(actions: list[dict]) -> dict:
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

        base = {"description": description, "command": command, "risk": risk}

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

        # All checks passed — execute
        raw = run_cli(command)
        executed.append({
            **base,
            "result":  sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"],
            "success": raw["success"],
        })

    return {"steps": executed}
