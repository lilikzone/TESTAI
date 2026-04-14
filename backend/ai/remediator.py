"""
AI Remediator — Generates safe AWS CLI fix commands based on detected issues.
Uses AWS Bedrock to analyze issues and suggest remediation actions.

Output format:
    {
        "actions": [
            {
                "description": "Enable CloudWatch logging for VPN",
                "command": "aws ec2 modify-vpn-connection-options ...",
                "risk": "low"
            }
        ]
    }

Safe list policy:
    Only commands that ENABLE, MODIFY, TAG, or PUT configuration are allowed.
    No delete, terminate, remove, or destructive operations.
"""

import json
import os

import boto3

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Commands allowed in remediation output — prefix-based safe list
_SAFE_COMMAND_PREFIXES = (
    "aws ec2 modify-",
    "aws ec2 enable-",
    "aws ec2 create-tags",
    "aws ec2 associate-",
    "aws logs create-log-group",
    "aws logs put-retention-policy",
    "aws cloudwatch put-metric-alarm",
    "aws cloudwatch enable-alarm-actions",
    "aws s3api put-bucket-versioning",
    "aws s3api put-bucket-encryption",
    "aws s3api put-public-access-block",
    "aws iam update-account-password-policy",
    "aws iam tag-",
    "aws lambda update-function-configuration",
    "aws rds modify-db-instance",
    "aws rds modify-db-cluster",
    "aws sns create-topic",
    "aws sns subscribe",
)

# Keywords that must never appear in remediation commands
_BLOCKED_KEYWORDS = (
    "delete", "terminate", "remove", "purge", "destroy",
    "detach", "disassociate", "revoke", "deregister",
)

_SYSTEM_PROMPT = """\
You are a senior AWS cloud engineer performing remediation.
Based on the analysis result provided, generate a list of safe fix commands.

Output rules:
- Return ONLY a valid JSON object: {"actions": [...]}
- Each action must have: "description", "command", "risk"
- risk values: "low", "medium", "high"
- Only suggest SAFE commands: modify, enable, tag, put, create-log-group, put-metric-alarm
- NEVER suggest: delete, terminate, remove, purge, destroy, detach, revoke
- Commands must be real AWS CLI commands
- No placeholders — use generic resource references where ID is unknown
- No markdown, no explanation outside JSON
- Maximum 5 actions

Risk classification:
- low    = read-only config change, enabling logging/monitoring
- medium = modifying encryption, access policies
- high   = changing network config, security groups

Example output:
{
  "actions": [
    {
      "description": "Enable CloudWatch logging for VPN tunnel",
      "command": "aws ec2 modify-vpn-connection-options --vpn-connection-id vpn-xxxxxxxx --local-ipv4-network-cidr 0.0.0.0/0",
      "risk": "low"
    },
    {
      "description": "Create CloudWatch alarm for VPN tunnel state",
      "command": "aws cloudwatch put-metric-alarm --alarm-name VPN-TunnelState --metric-name TunnelState --namespace AWS/VPN --statistic Average --period 300 --threshold 1 --comparison-operator LessThanThreshold --evaluation-periods 1 --alarm-actions arn:aws:sns:ap-southeast-3:123456789:alerts",
      "risk": "low"
    }
  ]
}

Analysis to remediate:"""


def _get_bedrock_client():
    region  = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("bedrock-runtime")


def _is_safe_action(command: str) -> bool:
    """Validate a command against the safe list and blocked keywords."""
    cmd_lower = command.lower().strip()

    # Must start with a safe prefix
    if not any(cmd_lower.startswith(prefix) for prefix in _SAFE_COMMAND_PREFIXES):
        return False

    # Must not contain blocked keywords
    if any(kw in cmd_lower for kw in _BLOCKED_KEYWORDS):
        return False

    return True


def generate_remediation(analysis: str) -> dict:
    """
    Generate safe AWS CLI remediation actions based on an analysis result.

    Args:
        analysis: Text output from formatter.format_result() or format_steps(),
                  describing detected issues in the AWS environment.

    Returns:
        dict: {"actions": [...]} where each action has:
              description (str), command (str), risk (str: low/medium/high)

    Raises:
        RuntimeError: If Bedrock invocation fails.
        ValueError:   If the model returns invalid JSON.
    """
    if not analysis or not analysis.strip():
        return {"actions": []}

    prompt = _SYSTEM_PROMPT + "\n" + analysis.strip()[:3000]

    client = _get_bedrock_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    })

    try:
        response = client.invoke_model(
            modelId=_BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
    except Exception as e:
        raise RuntimeError(f"Bedrock invocation failed: {str(e)}")

    raw = json.loads(response["body"].read())["content"][0]["text"].strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Extract first JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in response: {raw}")

    try:
        result = json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from model: {e}\nRaw: {raw}")

    if "actions" not in result:
        raise ValueError(f"Missing 'actions' key in response: {result}")

    # Filter: keep only safe actions, cap at 5
    safe_actions = []
    for action in result["actions"][:5]:
        if not isinstance(action, dict):
            continue
        command = action.get("command", "").strip()
        if not command.startswith("aws "):
            continue
        if not _is_safe_action(command):
            action["command"] = f"# BLOCKED (unsafe): {command}"
            action["risk"] = "blocked"
        safe_actions.append(action)

    return {"actions": safe_actions}
