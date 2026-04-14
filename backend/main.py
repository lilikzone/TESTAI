"""
AI Cloud Operator — Backend Entry Point
FastAPI server with clean pipeline: translate → validate → execute → format
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services import ai_service, cli_executor, formatter
from backend.services.sanitizer import sanitize_aws_output
from backend.services.planner import plan_actions
from backend.services.orchestrator import run_ai_agent
from backend.utils.security import is_safe_command

load_dotenv()

# Log active configuration on startup
print(f"[CONFIG] AWS_PROFILE={os.getenv('AWS_PROFILE', 'sandbox')} | AWS_REGION={os.getenv('AWS_REGION', 'ap-southeast-3')} | BEDROCK_REGION={os.getenv('BEDROCK_REGION', 'us-east-1')}")

app = FastAPI(
    title="AI Cloud Operator",
    description="Operate AWS using natural language powered by Gemini AI",
    version="0.1.0",
)


# --------------------------------------------------------------------------- #
# Global error handler
# --------------------------------------------------------------------------- #

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _log("ERROR", f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error.", "detail": str(exc)},
    )


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    command: str | None
    answer: str
    raw: str | None = None


class PlanRequest(BaseModel):
    message: str


class PlanResponse(BaseModel):
    steps: list[dict]


class AgentRequest(BaseModel):
    message: str


class AgentResponse(BaseModel):
    steps: list[dict]
    final_answer: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _log(level: str, msg: str):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}] [{level}] {msg}")


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
      1. Receive message from user
      2. Generate AWS CLI command via Gemini (ai_service.generate_cli)
      3. Validate command safety (security.is_safe_command)
      4. Execute command via AWS CLI (cli_executor.run_cli)
      5. Format output into human-readable answer (formatter.format_result)
    """
    message = request.message.strip()
    _log("INFO", f"Received message: {message}")

    # Step 1 — Generate CLI command
    try:
        command = ai_service.generate_cli(message)
        _log("INFO", f"Generated command: {command}")
    except EnvironmentError as e:
        _log("ERROR", f"Environment error: {e}")
        return ChatResponse(command=None, answer=str(e))
    except ValueError as e:
        _log("WARN", f"AI returned unexpected output: {e}")
        return ChatResponse(command=None, answer=str(e))
    except Exception as e:
        _log("ERROR", f"AI translation failed: {e}")
        return ChatResponse(command=None, answer=f"Failed to generate CLI command: {str(e)}")

    # Step 2 — Security check
    if not is_safe_command(command):
        _log("WARN", f"Blocked unsafe command: {command}")
        return ChatResponse(
            command=command,
            answer=(
                "⚠️ Command requires approval before execution.\n"
                f"Detected potentially destructive operation in: `{command}`\n"
                "Please review and confirm with your administrator."
            ),
        )

    _log("INFO", f"Command passed security check (risk: safe)")

    # Step 3 — Execute
    result = cli_executor.run_cli(command)
    _log("INFO", f"Execution success={result['success']}")

    if not result["success"]:
        _log("WARN", f"CLI execution error: {result['error']}")
        return ChatResponse(
            command=command,
            answer=f"AWS CLI execution failed:\n{result['error']}",
            raw=result["output"] or None,
        )

    # Step 4 — Sanitize before sending to AI
    sanitized = sanitize_aws_output(result["output"])
    _log("INFO", f"Output sanitized ({len(result['output'])} → {len(sanitized)} chars)")

    # Step 5 — Format
    try:
        answer = formatter.format_result(sanitized)
        _log("INFO", "Response formatted successfully")
    except Exception as e:
        _log("ERROR", f"Formatter failed: {e}")
        answer = sanitized  # fallback to sanitized output

    return ChatResponse(
        command=command,
        answer=answer,
        raw=sanitized,
    )

@app.post("/ai/plan", response_model=PlanResponse)
def plan(request: PlanRequest):
    """
    Action planner endpoint.
    Breaks down a user request into ordered AWS CLI steps.
    """
    message = request.message.strip()
    _log("INFO", f"Plan request: {message}")

    try:
        result = plan_actions(message)
        _log("INFO", f"Plan generated: {len(result['steps'])} steps")
        return PlanResponse(steps=result["steps"])
    except (RuntimeError, ValueError) as e:
        _log("ERROR", f"Planner failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/ai/agent", response_model=AgentResponse)
def agent(request: AgentRequest):
    """
    Full AI agent endpoint.
    Plans, executes, sanitizes, and analyzes AWS operations autonomously.
    """
    message = request.message.strip()
    _log("INFO", f"Agent request: {message}")

    try:
        result = run_ai_agent(message)
        _log("INFO", f"Agent completed: {len(result['steps'])} steps executed")
        return AgentResponse(
            steps=result["steps"],
            final_answer=result["final_answer"],
        )
    except Exception as e:
        _log("ERROR", f"Agent failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
