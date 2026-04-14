"""
RBAC — Role-Based Access Control for AI remediation actions.

Roles and permissions:
    viewer  → read-only, cannot execute any remediation
    operator → can execute low and medium risk actions
    admin   → can execute all risk levels including high

Risk levels:
    low     → safe config changes (enable logging, create alarms)
    medium  → moderate changes (modify encryption, access policies)
    high    → impactful changes (network config, security groups)
    blocked → always rejected regardless of role
"""

# Maps role → maximum risk level allowed
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer":   [],
    "operator": ["low", "medium"],
    "admin":    ["low", "medium", "high"],
}

# Default role if not specified
_DEFAULT_ROLE = "operator"


def get_allowed_risks(role: str) -> list[str]:
    """Return the list of risk levels allowed for a given role."""
    return _ROLE_PERMISSIONS.get(role.lower(), _ROLE_PERMISSIONS[_DEFAULT_ROLE])


def can_execute(role: str, risk: str) -> bool:
    """
    Check whether a role is permitted to execute an action of a given risk level.

    Args:
        role: User role — "viewer", "operator", or "admin".
        risk: Action risk level — "low", "medium", "high", or "blocked".

    Returns:
        bool: True if the role is allowed to execute this risk level.
    """
    if risk == "blocked":
        return False
    return risk.lower() in get_allowed_risks(role.lower())


def check_permission(role: str, action: dict) -> tuple[bool, str]:
    """
    Validate whether a role can execute a specific action.

    Args:
        role:   User role string.
        action: Action dict with at least a "risk" key.

    Returns:
        tuple[bool, str]: (allowed, reason)
            allowed = True if execution is permitted
            reason  = explanation string (empty if allowed)
    """
    risk = action.get("risk", "unknown").lower()

    if risk == "blocked":
        return False, "Action is permanently blocked regardless of role."

    if risk == "unknown":
        return False, "Action has unknown risk level — cannot execute without classification."

    allowed_risks = get_allowed_risks(role)

    if not allowed_risks:
        return False, f"Role '{role}' has no execution permissions."

    if risk not in allowed_risks:
        return False, (
            f"Role '{role}' is not permitted to execute '{risk}' risk actions. "
            f"Required role: admin."
            if risk == "high"
            else
            f"Role '{role}' is not permitted to execute '{risk}' risk actions."
        )

    return True, ""
