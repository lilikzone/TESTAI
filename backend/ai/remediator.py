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

import hashlib
import json
import os
import uuid

import boto3

from backend.ai.safe_commands import is_safe, is_blocked

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

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
    """Validate using centralized safe_commands registry."""
    return is_safe(command) and not is_blocked(command)

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


def _sign_action(action: dict) -> dict:
    """
    Add action_id (UUID) and hash (SHA256 of command) to an action dict.
    Used to verify integrity on /ai/approve — prevents tampering.
    """
    command = action.get("command", "")
    return {
        **action,
        "action_id": str(uuid.uuid4()),
        "hash":      hashlib.sha256(command.encode()).hexdigest(),
    }


def sign_actions(result: dict) -> dict:
    """
    Sign all actions in a remediation result with action_id and hash.

    Args:
        result: Output from generate_remediation() — {"actions": [...]}

    Returns:
        Same structure with each action enriched with action_id and hash.
    """
    return {
        "actions": [_sign_action(a) for a in result.get("actions", [])]
    }
