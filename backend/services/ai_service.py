"""
AI Service — Gemini integration for translation and formatting.
Handles two responsibilities:
  1. translate()  — natural language → AWS CLI command
  2. format_output() — raw AWS JSON → human-readable summary
"""

import os
from pathlib import Path

import google.generativeai as genai

# Load prompts once at module level
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _get_client() -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in environment variables.")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    return genai.GenerativeModel(model_name)


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
