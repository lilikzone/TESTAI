"""
Formatter Service — Analyzes sanitized AWS CLI output using AWS Bedrock.
"""

import json
import os
import re

import boto3

from backend.services import ai_service

_MAX_INPUT_CHARS = 2000
_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def _get_bedrock_client():
    region  = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("bedrock-runtime")


def _invoke_bedrock(prompt: str, max_tokens: int = 800) -> str:
    client = _get_bedrock_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
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
    return json.loads(response["body"].read())["content"][0]["text"].strip()


# --------------------------------------------------------------------------- #
# format_result — primary function used by /ai/chat pipeline
# --------------------------------------------------------------------------- #

_FORMAT_RESULT_PROMPT = """\
You are a senior AWS cloud engineer.
Analyze the AWS CLI output and provide:

Summary:
- What resources exist (count, type)

Status:
- Are they UP / DOWN / HEALTHY

Risks:
- Misconfiguration
- Missing logging
- Weak security

Recommendations:
- Clear and actionable steps

Rules:
- Be specific (include numbers)
- Do NOT be generic
- Do NOT repeat raw data
- Answer in Bahasa Indonesia

AWS CLI output:
{clean_output}"""


def format_result(clean_output: str) -> str:
    """
    Analyze sanitized AWS CLI output and return a senior cloud engineer insight.

    Input is capped at 2000 characters. Returns clean text — no JSON.

    Args:
        clean_output: Sanitized AWS CLI output string (from sanitizer.py).

    Returns:
        str: Analysis covering summary, status, risks, and recommendations
             in Bahasa Indonesia.

    Raises:
        RuntimeError: If Bedrock invocation fails.
    """
    if not clean_output or not clean_output.strip():
        return "Tidak ada output yang diterima dari AWS CLI."

    # Cap input at 2000 characters
    truncated = clean_output.strip()[:_MAX_INPUT_CHARS]
    if len(clean_output.strip()) > _MAX_INPUT_CHARS:
        truncated += "\n... [output truncated]"

    prompt = _FORMAT_RESULT_PROMPT.format(clean_output=truncated)
    return _invoke_bedrock(prompt, max_tokens=800)


# --------------------------------------------------------------------------- #
# analyze_results — used by orchestrator for multi-step analysis
# --------------------------------------------------------------------------- #

_ANALYZE_RESULTS_PROMPT = """\
You are a senior cloud engineer.
You are given multiple AWS CLI outputs.
Analyze and provide:
- Overall summary
- Health status
- Risks
- Recommendations

Be specific, use numbers, avoid generic text.
Respond entirely in Bahasa Indonesia.

AWS CLI outputs:
{combined_outputs}"""


def analyze_results(all_results: list[str]) -> str:
    """
    Analyze multiple sanitized AWS CLI outputs and return a final insight.

    Args:
        all_results: List of sanitized AWS CLI output strings.

    Returns:
        str: Final AI-generated insight in Bahasa Indonesia.
    """
    if not all_results:
        return "Tidak ada output yang diterima untuk dianalisis."

    combined = ""
    for i, output in enumerate(all_results, 1):
        preview = output.strip()[:3000]
        if len(output.strip()) > 3000:
            preview += "\n... [truncated]"
        combined += f"\n--- Output {i} ---\n{preview}\n"

    prompt = _ANALYZE_RESULTS_PROMPT.format(combined_outputs=combined)
    return _invoke_bedrock(prompt, max_tokens=1024)


# --------------------------------------------------------------------------- #
# format_response — used by /ai/chat full pipeline variant
# --------------------------------------------------------------------------- #

def _extract_service(command: str) -> str:
    match = re.match(r"aws\s+(\S+)", command)
    return match.group(1) if match else "aws"


def format_response(raw_output: str, original_query: str, executed_command: str) -> str:
    """Format raw AWS output using the prompt-file based ai_service pipeline."""
    if not raw_output or raw_output.strip() == "":
        return "The command executed successfully but returned no output."

    aws_service_name = _extract_service(executed_command)
    try:
        return ai_service.format_output(
            raw_output=raw_output,
            original_query=original_query,
            aws_service=aws_service_name,
        )
    except Exception as e:
        return f"[Formatter unavailable: {str(e)}]\n\nRaw output:\n{raw_output}"


# --------------------------------------------------------------------------- #
# format_steps — accepts multi-step executor output
# --------------------------------------------------------------------------- #

_FORMAT_STEPS_PROMPT = """\
You are a senior AWS cloud engineer.
You are given results from multiple AWS CLI commands executed in sequence.
Correlate the data across all steps and provide a unified analysis.

Structure your response exactly as:

**Ringkasan**
(What was found across all steps — resource names, counts, types)

**Status**
(Health of each resource — UP/DOWN/HEALTHY/ISSUE with specific values)

**Risiko**
(Misconfigurations, missing logging, weak security, or anomalies found)

**Rekomendasi**
(Specific, actionable steps — reference actual resource names/IDs)

Rules:
- Correlate data across steps (e.g. VPN state + CloudWatch metrics together)
- Do NOT repeat raw CLI output or JSON
- Be concise and specific — use numbers, names, IPs
- Answer entirely in Bahasa Indonesia

Step results:
{steps_summary}"""


def format_steps(steps: list[dict]) -> str:
    """
    Analyze multi-step executor results and return a unified cloud engineer insight.

    Accepts the output of backend/ai/executor.execute_plan() directly.

    Args:
        steps: List of executed step dicts, each with:
               step (int), command (str), result (str), success (bool)

    Returns:
        str: Unified analysis in Bahasa Indonesia covering summary,
             status, risks, and recommendations correlated across all steps.

    Raises:
        RuntimeError: If Bedrock invocation fails.
    """
    if not steps:
        return "Tidak ada hasil eksekusi yang diterima."

    # Build a concise summary of each step for the prompt
    steps_summary = ""
    for s in steps:
        steps_summary += f"\nStep {s['step']}: {s['command']}\n"
        if s["success"]:
            # Trim per-step result to avoid token overflow
            preview = s["result"].strip()[:1500]
            if len(s["result"].strip()) > 1500:
                preview += "\n... [truncated]"
            steps_summary += f"Output:\n{preview}\n"
        else:
            steps_summary += f"Error: {s['result']}\n"

    prompt = _FORMAT_STEPS_PROMPT.format(steps_summary=steps_summary)
    return _invoke_bedrock(prompt, max_tokens=1024)
