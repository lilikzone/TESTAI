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

    Each action is re-validated against safe_commands before execution —
    approval does not bypass the safety check.

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

        # Re-validate even after approval
        if not command.startswith("aws "):
            executed.append({**base, "result": "Skipped: not a valid AWS CLI command.", "success": False})
            continue

        if is_blocked(command) or not is_safe(command):
            executed.append({**base, "result": "Blocked: command failed safety re-validation.", "success": False})
            continue

        raw = run_cli(command)
        executed.append({
            **base,
            "result":  sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"],
            "success": raw["success"],
        })

    return {"steps": executed}
