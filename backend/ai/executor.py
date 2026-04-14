"""
AI Executor — Executes a list of planned AWS CLI commands and collects results.
Accepts output from backend/ai/planner.py (list of {"step", "action"} dicts).
"""

from backend.services.cli_executor import run_cli
from backend.services.sanitizer import sanitize_aws_output
from backend.utils.security import is_safe_command


def execute_plan(steps: list[dict]) -> dict:
    """
    Execute an ordered list of AWS CLI commands and collect sanitized results.

    Args:
        steps: List of step dicts from ai/planner.create_plan().
               Each item: {"step": int, "action": "aws ..."}

    Returns:
        dict with key "steps" — list of executed steps, each containing:
            step    (int)  — step number
            command (str)  — the AWS CLI command that was run
            result  (str)  — sanitized output or error message
            success (bool) — whether execution succeeded
    """
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

        # Execute
        raw = run_cli(command)

        if raw["success"]:
            result = sanitize_aws_output(raw["output"])
        else:
            result = raw["error"] or "Command failed with no error message."

        executed.append({
            "step":    step_num,
            "command": command,
            "result":  result,
            "success": raw["success"],
        })

    return {"steps": executed}
