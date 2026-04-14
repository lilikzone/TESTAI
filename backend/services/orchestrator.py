"""
Orchestrator — Runs a full AI agent loop:
  1. planner   → break user request into steps
  2. executor  → run each AWS CLI command
  3. sanitizer → strip secrets from output
  4. analyzer  → synthesize all results into a final answer
"""

from backend.services import ai_service, cli_executor
from backend.services.planner import plan_actions
from backend.services.sanitizer import sanitize_aws_output
from backend.utils.security import is_safe_command


def run_ai_agent(user_input: str) -> dict:
    """
    Execute a full AI agent loop for a user request.

    Args:
        user_input: Natural language request from the user.

    Returns:
        dict:
            steps        — list of executed steps with description, command,
                           success flag, and sanitized output
            final_answer — AI-generated synthesis of all step results
    """

    # Step 1 — Plan
    plan = plan_actions(user_input)
    steps_plan = plan.get("steps", [])

    executed_steps = []

    # Step 2 — Execute each step
    for step in steps_plan:
        description = step.get("description", "")
        command     = step.get("command", "").strip()

        step_result = {
            "description": description,
            "command":     command,
            "success":     False,
            "output":      "",
            "error":       "",
        }

        # Skip empty or non-AWS commands
        if not command.startswith("aws "):
            step_result["error"] = "Skipped: not a valid AWS CLI command."
            executed_steps.append(step_result)
            continue

        # Security check
        if not is_safe_command(command):
            step_result["error"] = "Blocked: command contains destructive keyword."
            executed_steps.append(step_result)
            continue

        # Execute
        result = cli_executor.run_cli(command)
        step_result["success"] = result["success"]

        if result["success"]:
            # Sanitize output before storing
            step_result["output"] = sanitize_aws_output(result["output"])
        else:
            step_result["error"] = result["error"]

        executed_steps.append(step_result)

    # Step 3 — Analyze all results
    final_answer = ai_service.analyze(
        user_input=user_input,
        steps=executed_steps,
    )

    return {
        "steps":        executed_steps,
        "final_answer": final_answer,
    }
