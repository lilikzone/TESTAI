"""
AI Cloud Operator — Backend Entry Point
FastAPI server with clean pipeline: validate → translate → execute → format
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.services import ai_service, cli_executor, formatter
from backend.utils.security import validate

load_dotenv()

app = FastAPI(
    title="AI Cloud Operator",
    description="Operate AWS using natural language powered by Gemini AI",
    version="0.1.0",
)

AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-3")


# --------------------------------------------------------------------------- #
# Request / Response schemas
# --------------------------------------------------------------------------- #

class ChatRequest(BaseModel):
    query: str
    region: str | None = None
    confirm: bool = False  # set True to approve DESTRUCTIVE commands


class ChatResponse(BaseModel):
    query: str
    command: str | None
    risk_level: str
    output: str
    requires_confirmation: bool


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get("/")
def root():
    return {"status": "ok", "message": "AI Cloud Operator is running"}


@app.post("/ai/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main pipeline endpoint.

    Flow:
      1. Translate natural language → AWS CLI command (Gemini)
      2. Validate command through Guardrail (security)
      3. Execute command via AWS CLI
      4. Format raw output into human-readable summary (Gemini)
    """
    region = request.region or AWS_REGION

    # Step 1 — Translate
    try:
        command = ai_service.translate(
            query=request.query,
            aws_region=region,
        )
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI translation failed: {str(e)}")

    # Handle Gemini returning CLARIFY or UNSUPPORTED
    if command.startswith("CLARIFY:"):
        return ChatResponse(
            query=request.query,
            command=None,
            risk_level="NONE",
            output=command,
            requires_confirmation=False,
        )
    if command.startswith("UNSUPPORTED:"):
        return ChatResponse(
            query=request.query,
            command=None,
            risk_level="NONE",
            output=command,
            requires_confirmation=False,
        )

    # Step 2 — Validate
    validation = validate(command)

    if not validation.allowed and not validation.requires_confirmation:
        # Hard block
        return ChatResponse(
            query=request.query,
            command=command,
            risk_level=validation.risk_level,
            output=f"🚫 Blocked: {validation.reason}",
            requires_confirmation=False,
        )

    if validation.requires_confirmation and not request.confirm:
        # Destructive — needs explicit confirm=true
        return ChatResponse(
            query=request.query,
            command=command,
            risk_level=validation.risk_level,
            output=(
                f"⚠️ This command requires confirmation:\n`{command}`\n\n"
                f"{validation.reason}\n\n"
                "Resend the request with `\"confirm\": true` to proceed."
            ),
            requires_confirmation=True,
        )

    # Step 3 — Execute
    result = cli_executor.execute(command)

    if not result.success:
        return ChatResponse(
            query=request.query,
            command=command,
            risk_level=validation.risk_level,
            output=f"AWS execution error:\n{result.error}",
            requires_confirmation=False,
        )

    # Step 4 — Format
    summary = formatter.format_response(
        raw_output=result.output,
        original_query=request.query,
        executed_command=command,
    )

    return ChatResponse(
        query=request.query,
        command=command,
        risk_level=validation.risk_level,
        output=summary,
        requires_confirmation=False,
    )
