"""
Sanitizer — Strips sensitive fields and extracts only important fields
from AWS CLI output before sending to AI formatter.

Strategy:
  1. Parse JSON safely
  2. Detect resource type from top-level keys
  3. Extract only relevant fields per resource type
  4. Fall back to recursive sensitive-field removal for unknown types
  5. Return compact JSON string (no truncation that breaks structure)
"""

import json

_SENSITIVE_FIELDS = {"PreSharedKey", "CustomerGatewayConfiguration"}


# --------------------------------------------------------------------------- #
# Public helper
# --------------------------------------------------------------------------- #

def remove_sensitive_fields(data: dict | list) -> dict | list:
    """
    Recursively remove sensitive fields from a parsed JSON object or list.

    Args:
        data: Parsed JSON — dict or list.

    Returns:
        Cleaned structure with sensitive keys removed at all nesting levels.
    """
    if isinstance(data, dict):
        return {
            k: remove_sensitive_fields(v)
            for k, v in data.items()
            if k not in _SENSITIVE_FIELDS
        }
    if isinstance(data, list):
        return [remove_sensitive_fields(item) for item in data]
    return data


# --------------------------------------------------------------------------- #
# Per-resource extractors
# --------------------------------------------------------------------------- #

def _extract_vpn(vpn: dict) -> dict:
    """Extract only essential VPN connection fields."""
    telemetry = [
        {
            "OutsideIpAddress": t.get("OutsideIpAddress"),
            "Status":           t.get("Status"),
            "AcceptedRouteCount": t.get("AcceptedRouteCount"),
            "LastStatusChange": t.get("LastStatusChange"),
            "StatusMessage":    t.get("StatusMessage"),
            "LogOptions": {
                "CloudWatchLogOptions": {
                    "LogEnabled": (
                        t.get("LogOptions", {})
                         .get("CloudWatchLogOptions", {})
                         .get("LogEnabled", False)
                    )
                }
            },
        }
        for t in vpn.get("VgwTelemetry", [])
    ]

    return {
        "VpnConnectionId":      vpn.get("VpnConnectionId"),
        "State":                vpn.get("State"),
        "Type":                 vpn.get("Type"),
        "CustomerGatewayId":    vpn.get("CustomerGatewayId"),
        "VpnGatewayId":         vpn.get("VpnGatewayId"),
        "GatewayAssociationState": vpn.get("GatewayAssociationState"),
        "Tags":                 vpn.get("Tags", []),
        "VgwTelemetry":         telemetry,
        "Options": {
            "EnableAcceleration": vpn.get("Options", {}).get("EnableAcceleration"),
            "StaticRoutesOnly":   vpn.get("Options", {}).get("StaticRoutesOnly"),
        },
    }


def _extract_subnet(subnet: dict) -> dict:
    return {
        "SubnetId":               subnet.get("SubnetId"),
        "State":                  subnet.get("State"),
        "VpcId":                  subnet.get("VpcId"),
        "CidrBlock":              subnet.get("CidrBlock"),
        "AvailabilityZone":       subnet.get("AvailabilityZone"),
        "AvailableIpAddressCount": subnet.get("AvailableIpAddressCount"),
        "MapPublicIpOnLaunch":    subnet.get("MapPublicIpOnLaunch"),
        "Tags":                   subnet.get("Tags", []),
    }


def _extract_instance(instance: dict) -> dict:
    return {
        "InstanceId":   instance.get("InstanceId"),
        "InstanceType": instance.get("InstanceType"),
        "State":        instance.get("State", {}).get("Name"),
        "PublicIpAddress":  instance.get("PublicIpAddress"),
        "PrivateIpAddress": instance.get("PrivateIpAddress"),
        "LaunchTime":   instance.get("LaunchTime"),
        "Tags":         instance.get("Tags", []),
    }


def _extract_s3_bucket(bucket: dict) -> dict:
    return {
        "Name":         bucket.get("Name"),
        "CreationDate": bucket.get("CreationDate"),
    }


def _extract_lambda(fn: dict) -> dict:
    return {
        "FunctionName": fn.get("FunctionName"),
        "Runtime":      fn.get("Runtime"),
        "MemorySize":   fn.get("MemorySize"),
        "Timeout":      fn.get("Timeout"),
        "LastModified": fn.get("LastModified"),
        "State":        fn.get("State"),
    }


# --------------------------------------------------------------------------- #
# Main dispatcher
# --------------------------------------------------------------------------- #

def _extract_important_fields(parsed: dict) -> dict:
    """
    Detect resource type and extract only important fields.
    Falls back to sensitive-field removal for unknown resource types.
    """
    if "VpnConnections" in parsed:
        return {"VpnConnections": [_extract_vpn(v) for v in parsed["VpnConnections"]]}

    if "Subnets" in parsed:
        return {"Subnets": [_extract_subnet(s) for s in parsed["Subnets"]]}

    if "Reservations" in parsed:
        instances = [
            _extract_instance(i)
            for r in parsed["Reservations"]
            for i in r.get("Instances", [])
        ]
        return {"Instances": instances}

    if "Buckets" in parsed:
        return {"Buckets": [_extract_s3_bucket(b) for b in parsed["Buckets"]]}

    if "Functions" in parsed:
        return {"Functions": [_extract_lambda(f) for f in parsed["Functions"]]}

    # Unknown resource type — fall back to removing sensitive fields only
    return remove_sensitive_fields(parsed)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def sanitize_aws_output(raw_output: str) -> str:
    """
    Parse, extract important fields, and return a compact JSON string.

    For known resource types (VPN, Subnet, EC2, S3, Lambda):
      - Extracts only the fields needed for AI analysis
      - Removes sensitive fields (PreSharedKey, CustomerGatewayConfiguration)
      - No truncation — structure is always complete

    For unknown types:
      - Removes sensitive fields recursively
      - Returns compact JSON

    For non-JSON input:
      - Returns raw string trimmed to 2000 chars

    Args:
        raw_output: Raw stdout string from AWS CLI execution.

    Returns:
        str: Compact, sanitized JSON string safe to send to AI models.
    """
    if not raw_output or not raw_output.strip():
        return ""

    try:
        parsed = json.loads(raw_output)
        cleaned = _extract_important_fields(parsed)
        return json.dumps(cleaned, separators=(",", ":"))
    except json.JSONDecodeError:
        # Plain text output — trim to 2000 chars
        return raw_output.strip()[:2000]
