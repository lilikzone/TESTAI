"""
Risk Classifier — Classifies AWS CLI commands by risk level.
Used by executor.py to determine execution policy.
"""

HIGH_RISK = [
    "delete-db-instance",
    "terminate-instances",
    "delete-vpn-connection",
    "delete-security-group",
    "delete-subnet",
    "delete-vpc",
    "delete-internet-gateway",
    "delete-route-table",
    "delete-network-acl",
    "delete-key-pair",
    "delete-snapshot",
    "delete-volume",
    "delete-bucket",
    "delete-function",
    "delete-stack",
    "delete-cluster",
]

MEDIUM_RISK = [
    "stop-instances",
    "modify-vpn-connection-options",
    "modify-vpn-connection",
    "reboot-instances",
    "create-snapshot",
    "modify-db-instance",
    "modify-db-cluster",
    "update-function-configuration",
    "put-bucket-versioning",
    "put-bucket-encryption",
    "put-public-access-block",
    "put-metric-alarm",
    "create-log-group",
    "put-retention-policy",
]

LOW_RISK = [
    "describe-",
    "list-",
    "get-",
    "create-tags",
    "start-instances",
    "run-instances",
    "create-image",
]


def classify(command: str) -> str:
    """
    Classify an AWS CLI command as HIGH, MEDIUM, or LOW risk.

    Args:
        command: Full AWS CLI command string.

    Returns:
        str: "HIGH", "MEDIUM", or "LOW"
    """
    for c in HIGH_RISK:
        if c in command:
            return "HIGH"
    for c in MEDIUM_RISK:
        if c in command:
            return "MEDIUM"
    return "LOW"
