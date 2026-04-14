"""
AI Service — Gemini integration for translation and formatting.
Handles three responsibilities:
  1. generate_cli()   — natural language → AWS CLI command (simple, direct)
  2. translate()      — natural language → AWS CLI command (prompt-file based)
  3. format_output()  — raw AWS JSON → human-readable summary
"""

import os
import re
from pathlib import Path

import google.generativeai as genai

# Load prompts once at module level
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_GENERATE_CLI_SYSTEM_PROMPT = (
    "You are an AWS CLI expert. Convert user request into AWS CLI command. "
    "Rules:\n"
    "- Output ONLY the command\n"
    "- No explanation\n"
    "- No markdown formatting\n"
    "- No code blocks\n"
    "- No extra whitespace or newlines"
)


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _get_client() -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in environment variables.")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    return genai.GenerativeModel(model_name)


def _clean_command(text: str) -> str:
    """Strip whitespace, markdown fences, and ensure output is a single clean line."""
    text = text.strip()
    # Remove markdown code fences (```bash ... ``` or ``` ... ```)
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```$", "", text)
    # Collapse internal newlines/extra spaces into a single line
    text = " ".join(text.split())
    return text


def generate_cli(user_input: str) -> str:
    """
    Convert a natural language request into an AWS CLI command.

    Uses a concise system prompt that instructs Gemini to output
    only the command — no explanation, no markdown, no extra text.

    Args:
        user_input: Plain language description of the desired AWS operation.

    Returns:
        str: A clean, single-line AWS CLI command string.

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
        ValueError: If Gemini returns an empty or non-AWS response.
    """
    model = _get_client()
    prompt = f"{_GENERATE_CLI_SYSTEM_PROMPT}\n\nUser request: {user_input}"
    response = model.generate_content(prompt)
    command = _clean_command(response.text)

    if not command:
        raise ValueError("Gemini returned an empty response.")
    if not command.startswith("aws "):
        raise ValueError(f"Unexpected response from AI (not an AWS command): {command}")

    return command


def translate(query: str, aws_region: str, account_id: str = "unknown") -> str:
    """
    Translate a natural language query into an AWS CLI command string.

    Returns:
        str: AWS CLI command, or a string starting with CLARIFY: / UNSUPPORTED:
    """
    prompt_template = _load_prompt("translator.txt")
    prompt = prompt_template.format(
        user_query=query,
        aws_region=aws_region,
        account_id=account_id,
    )
    model = _get_client()
    response = model.generate_content(prompt)
    return response.text.strip()


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
    model = _get_client()
    response = model.generate_content(prompt)
    return response.text.strip()
