"""
Enterprise-Grade Execution Engine — AI Cloud Operator

Execution policy (in order):
  1. MAX_ACTIONS guard       — prevent blast radius
  2. BLOCK CHECK             — hard stop on blocked keywords
  3. SAFE CHECK              — must be in safe command list
  4. RISK CLASSIFICATION     — HIGH / MEDIUM / LOW
  5. HIGH RISK gate          — always REQUIRES_APPROVAL, never auto-execute
  6. DRY-RUN VALIDATION      — if supported, validate IAM permission first
  7. NO DRY-RUN + MEDIUM     — BLOCKED (cannot safely validate)
  8. REAL EXECUTION          — only LOW risk or MEDIUM with dry-run passed
  9. AUDIT LOG               — every outcome recorded

Output format (always structured):
  {
    "command": "...",
    "status":  "SUCCESS | FAILED | BLOCKED | REJECTED | REQUIRES_APPROVAL",
    "risk":    "LOW | MEDIUM | HIGH",
    "reason":  "...",
    "output":  "..."
  }
"""

import hashlib

from backend.ai.audit import log_action
from backend.ai.rbac import check_permission
from backend.ai.risk import classify
from backend.ai.safe_commands import is_blocked, is_safe
from backend.services.cli_executor import run_cli
from backend.services.sanitizer import sanitize_aws_output
from backend.utils.security import is_safe_command

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

MAX_ACTIONS = 5

DRY_RUN_SUPPORTED = [
    "start-instances",
    "stop-instances",
    "run-instances",
    "create-tags",
    "create-image",
    "create-snapshot",
    "reboot-instances",
    "terminate-instances",
    "associate-address",
    "disassociate-address",
    "modify-instance-attribute",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def is_valid_command(command: str) -> bool:
    """Return True if command contains no shell injection characters."""
    forbidden = [";", "&&", "|"]
    return not any(f in command for f in forbidden)


def supports_dry_run(command: str) -> bool:
    """Return True if the command supports AWS --dry-run flag."""
    return any(cmd in command for cmd in DRY_RUN_SUPPORTED)


def _dry_run(command: str) -> tuple[bool, str]:
    """
    Attempt dry-run. Returns (would_succeed, message).

    AWS returns DryRunOperation (exit 255) when permission check passes.
    UnauthorizedOperation means no IAM permission.
    Any other error means the real call would also fail.
    """
    result = run_cli(f"{command} --dry-run")
    combined = (result.get("error") or "") + (result.get("output") or "")

    if "DryRunOperation" in combined:
        return True, "Dry-run passed: IAM permission check succeeded."
    if "UnauthorizedOperation" in combined:
        return False, "Dry-run failed: insufficient IAM permissions."
    return False, f"Dry-run failed: {combined[:200]}"


def _make_result(command: str, status: str, risk: str = "LOW",
                 reason: str = "", output: str = "") -> dict:
    """Build a standardized result dict."""
    return {
        "command": command,
        "status":  status,
        "risk":    risk,
        "reason":  reason,
        "output":  output,
    }


# --------------------------------------------------------------------------- #
# execute_plan — read/describe pipeline (no approval needed)
# --------------------------------------------------------------------------- #

def execute_plan(steps: list[dict], remediation_actions: list[dict] | None = None) -> dict:
    """
    Execute an ordered list of read/describe AWS CLI commands.

    If remediation_actions are provided, returns a pending approval response
    without executing anything.

    Args:
        steps:               List of {"step", "action"} dicts from planner.
        remediation_actions: If present, triggers approval gate.

    Returns:
        {"steps": [...]}  or  {"needs_approval": True, "actions": [...]}
    """
    if remediation_actions:
        return {"needs_approval": True, "actions": remediation_actions}

    executed = []

    for item in steps:
        step_num = item.get("step", len(executed) + 1)
        command  = item.get("action", "").strip()

        if not command.startswith("aws "):
            executed.append({
                "step": step_num, "command": command,
                "result": "Skipped: not a valid AWS CLI command.", "success": False,
            })
            continue

        if not is_safe_command(command):
            executed.append({
                "step": step_num, "command": command,
                "result": "Blocked: command contains a destructive keyword.", "success": False,
            })
            continue

        raw         = run_cli(command)
        result_text = sanitize_aws_output(raw["output"]) if raw["success"] else raw["error"]

        log_action(user="system", command=command, result=result_text,
                   status="success" if raw["success"] else "failed")

        executed.append({
            "step": step_num, "command": command,
            "result": result_text, "success": raw["success"],
        })

    return {"steps": executed}


# --------------------------------------------------------------------------- #
# execute_approved — enterprise execution engine
# --------------------------------------------------------------------------- #

def execute_approved(actions: list[dict], user: str = "system", role: str = "operator") -> dict:
    """
    Enterprise-grade execution of approved remediation actions.

    Full validation pipeline per action:
      -1. RBAC check
       0. Hash tamper detection
       1. MAX_ACTIONS blast-radius guard
       2. Shell injection check
       3. BLOCK CHECK (hard stop)
       4. SAFE CHECK
       5. RISK CLASSIFICATION
       6. HIGH RISK → REQUIRES_APPROVAL (never auto-execute)
       7. DRY-RUN (if supported) → fail if permission denied
       8. NO DRY-RUN + MEDIUM → BLOCKED
       9. REAL EXECUTION
      10. AUDIT LOG

    Args:
        actions: List of signed action dicts from remediator.
        user:    Identity of the approving user.
        role:    Role of the user (viewer / operator / admin).

    Returns:
        {"steps": [{"command", "status", "risk", "reason", "output"}, ...]}
    """
    results = []

    # Blast-radius guard
    if len(actions) > MAX_ACTIONS:
        return {
            "steps": [_make_result(
                command="(batch)",
                status="BLOCKED",
                reason=f"Too many actions: {len(actions)} exceeds MAX_ACTIONS={MAX_ACTIONS}.",
            )]
        }

    for action in actions:
        command     = action.get("command", "").strip()
        description = action.get("description", "")
        risk_hint   = action.get("risk", "")

        # ------------------------------------------------------------------ #
        # Layer -1: RBAC
        # ------------------------------------------------------------------ #
        allowed, rbac_reason = check_permission(role, action)
        if not allowed:
            msg = f"Rejected by RBAC: {rbac_reason}"
            log_action(user=user, command=command, result=msg, status="rejected",
                       action_id=action.get("action_id", ""), hash=action.get("hash", ""))
            results.append(_make_result(command, "REJECTED", risk_hint, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 0: Hash tamper detection
        # ------------------------------------------------------------------ #
        expected_hash = action.get("hash", "")
        if expected_hash:
            if hashlib.sha256(command.encode()).hexdigest() != expected_hash:
                msg = "Rejected: hash mismatch — command may have been tampered with."
                log_action(user=user, command=command, result=msg, status="rejected",
                           action_id=action.get("action_id", ""), hash=expected_hash)
                results.append(_make_result(command, "REJECTED", risk_hint, msg))
                continue

        # ------------------------------------------------------------------ #
        # Layer 1: Shell injection check
        # ------------------------------------------------------------------ #
        if not is_valid_command(command):
            msg = "Rejected: command contains forbidden characters (;, &&, |)."
            log_action(user=user, command=command, result=msg, status="rejected")
            results.append(_make_result(command, "REJECTED", risk_hint, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 2: BLOCK CHECK — hard stop
        # ------------------------------------------------------------------ #
        if is_blocked(command):
            msg = "Blocked: command contains a destructive keyword."
            log_action(user=user, command=command, result=msg, status="blocked")
            results.append(_make_result(command, "BLOCKED", risk_hint, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 3: SAFE CHECK
        # ------------------------------------------------------------------ #
        if not is_safe(command):
            msg = "Rejected: command is not in the approved safe command list."
            log_action(user=user, command=command, result=msg, status="rejected")
            results.append(_make_result(command, "REJECTED", risk_hint, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 4: RISK CLASSIFICATION
        # ------------------------------------------------------------------ #
        risk = classify(command)

        # ------------------------------------------------------------------ #
        # Layer 5: HIGH RISK → always require approval, never auto-execute
        # ------------------------------------------------------------------ #
        if risk == "HIGH":
            msg = "High-risk command requires explicit admin approval before execution."
            log_action(user=user, command=command, result=msg, status="requires_approval")
            results.append(_make_result(command, "REQUIRES_APPROVAL", risk, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 6: DRY-RUN VALIDATION (if supported)
        # ------------------------------------------------------------------ #
        if supports_dry_run(command):
            dry_ok, dry_msg = _dry_run(command)
            if not dry_ok:
                log_action(user=user, command=command, result=dry_msg, status="dry-run-failed",
                           action_id=action.get("action_id", ""))
                results.append(_make_result(command, "FAILED", risk, dry_msg))
                continue

        # ------------------------------------------------------------------ #
        # Layer 7: NO DRY-RUN SUPPORT + MEDIUM RISK → BLOCKED
        # ------------------------------------------------------------------ #
        elif risk == "MEDIUM":
            msg = "Blocked: medium-risk command has no dry-run support — cannot safely validate."
            log_action(user=user, command=command, result=msg, status="blocked")
            results.append(_make_result(command, "BLOCKED", risk, msg))
            continue

        # ------------------------------------------------------------------ #
        # Layer 8: REAL EXECUTION
        # ------------------------------------------------------------------ #
        raw         = run_cli(command)
        output_text = sanitize_aws_output(raw["output"]) if raw["success"] else ""
        error_text  = raw.get("error", "") if not raw["success"] else ""
        status      = "SUCCESS" if raw["success"] else "FAILED"
        reason      = error_text if not raw["success"] else ""

        # ------------------------------------------------------------------ #
        # Layer 9: AUDIT LOG
        # ------------------------------------------------------------------ #
        log_action(
            user=user, command=command,
            result=output_text or error_text,
            status=status.lower(),
            action_id=action.get("action_id", ""),
            hash=action.get("hash", ""),
        )

        results.append(_make_result(command, status, risk, reason, output_text))

    return {"steps": results}
