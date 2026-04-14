"""
Safe command registry for AI-generated remediation actions.
Used by remediator.py and executor.py to validate commands before execution.
"""

SAFE_COMMANDS = [
    "aws ec2 modify-vpn-connection-options",
    "aws ec2 start-instances",
    "aws ec2 stop-instances",
    "aws logs create-log-group",
    "aws logs put-retention-policy",
    "aws ec2 modify-vpn-connection",
    "aws ec2 create-tags",
    "aws ec2 enable-",
    "aws ec2 associate-",
    "aws cloudwatch put-metric-alarm",
    "aws cloudwatch enable-alarm-actions",
    "aws s3api put-bucket-versioning",
    "aws s3api put-bucket-encryption",
    "aws s3api put-public-access-block",
    "aws lambda update-function-configuration",
    "aws rds modify-db-instance",
    "aws rds modify-db-cluster",
    "aws sns create-topic",
    "aws sns subscribe",
]

BLOCKED_COMMANDS = [
    "delete",
    "terminate",
    "remove",
    "drop",
    "purge",
    "destroy",
    "detach",
    "revoke",
    "deregister",
    " rm ",
    "--recursive",
]


def is_safe(command: str) -> bool:
    """Return True if command starts with any entry in SAFE_COMMANDS."""
    return any(command.startswith(c) for c in SAFE_COMMANDS)


def is_blocked(command: str) -> bool:
    """Return True if command contains any blocked keyword (case-insensitive)."""
    return any(b in command.lower() for b in BLOCKED_COMMANDS)
