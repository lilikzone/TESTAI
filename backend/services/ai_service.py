"""
AI Service — AWS Bedrock integration for CLI translation and output formatting.
Handles three responsibilities:
  1. generate_cli()   — natural language → AWS CLI command (direct, simple)
  2. translate()      — natural language → AWS CLI command (prompt-file based)
  3. format_output()  — raw AWS JSON → human-readable summary
"""

import json
import os
import re
from pathlib import Path

import boto3

from backend.utils.regions import build_region_hint

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_GENERATE_CLI_SYSTEM_PROMPT = (
    "You are an AWS CLI expert. Convert user request into AWS CLI command. "
    "Rules:\n"
    "- Output ONLY the command\n"
    "- No explanation\n"
    "- No markdown formatting\n"
    "- No code blocks\n"
    "- No extra whitespace or newlines\n"
    f"{build_region_hint()}"
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _get_bedrock_client():
    # Bedrock Claude models are available in us-east-1
    # AWS CLI operations use AWS_REGION (ap-southeast-3)
    bedrock_region = os.getenv("BEDROCK_REGION", "us-east-1")
    profile = os.getenv("AWS_PROFILE", "sandbox")
    session = boto3.Session(profile_name=profile, region_name=bedrock_region)
    return session.client("bedrock-runtime")


def _invoke(prompt: str, max_tokens: int = 200) -> str:
    """
    Send a prompt to Bedrock Claude and return the response text.

    Args:
        prompt:     Full prompt string to send as user message.
        max_tokens: Maximum tokens in the response.

    Returns:
        str: Raw text response from the model.

    Raises:
        RuntimeError: If the Bedrock invocation fails for any reason.
    """
    client = _get_bedrock_client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {"role": "user", "content": prompt}
        ],
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

    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _clean_command(text: str) -> str:
    """Strip whitespace, markdown fences, and collapse to a single clean line."""
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# Public functions
# --------------------------------------------------------------------------- #

def generate_cli(user_input: str) -> str:
    """
    Convert a natural language request into an AWS CLI command via Bedrock.

    Args:
        user_input: Plain language description of the desired AWS operation.

    Returns:
        str: A clean, single-line AWS CLI command string.

    Raises:
        RuntimeError: If Bedrock invocation fails.
        ValueError:   If the model returns an empty or non-AWS response.
    """
    prompt = f"{_GENERATE_CLI_SYSTEM_PROMPT}\n\nUser request: {user_input}"
    raw = _invoke(prompt, max_tokens=200)
    command = _clean_command(raw)

    if not command:
        raise ValueError("Bedrock returned an empty response.")
    if not command.startswith("aws "):
        raise ValueError(f"Unexpected response from AI (not an AWS command): {command}")

    return command


def translate(query: str, aws_region: str, account_id: str = "unknown") -> str:
    """
    Translate a natural language query into an AWS CLI command string
    using the full prompt template from prompts/translator.txt.

    Returns:
        str: AWS CLI command, or a string starting with CLARIFY: / UNSUPPORTED:
    """
    prompt_template = _load_prompt("translator.txt")
    prompt = prompt_template.format(
        user_query=query,
        aws_region=aws_region,
        account_id=account_id,
    )
    return _invoke(prompt, max_tokens=300)


def format_output(raw_output: str, original_query: str, aws_service: str = "aws") -> str:
    """
    Summarize raw AWS JSON output into a human-readable insight.

    Returns:
        str: Formatted summary with optional recommendations.
    """
    prompt_template = _load_prompt("formatter.txt")
    prompt = prompt_template.format(
        original_query=original_query,
        aws_service=aws_service,
        raw_output=raw_output,
    )
    return _invoke(prompt, max_tokens=500)


def analyze(user_input: str, steps: list[dict]) -> str:
    """
    Synthesize results from multiple executed AWS CLI steps into a final answer.

    Args:
        user_input: The original user request for context.
        steps:      List of executed steps with description, command,
                    success flag, output, and error.

    Returns:
        str: Final AI-generated analysis in Bahasa Indonesia.
    """
    steps_summary = ""
    for i, step in enumerate(steps, 1):
        steps_summary += f"\nStep {i}: {step['description']}\n"
        steps_summary += f"  Command: {step['command']}\n"
        if step["success"]:
            output_preview = step["output"][:1000] + ("..." if len(step["output"]) > 1000 else "")
            steps_summary += f"  Output: {output_preview}\n"
        else:
            steps_summary += f"  Error: {step['error']}\n"

    prompt = f"""\
You are a senior AWS cloud engineer.
The user asked: "{user_input}"

The following AWS CLI steps were executed:
{steps_summary}

Analyze all results and provide a final answer in Bahasa Indonesia covering:
- Ringkasan keseluruhan (what was found across all steps)
- Status (any issues or errors)
- Risiko (if any)
- Rekomendasi (specific and actionable)

Be specific. Mention resource names, counts, IPs, and statuses.
Do NOT give generic advice."""

    return _invoke(prompt, max_tokens=1024)
