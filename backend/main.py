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

from backend.services import formatter
from backend.services.planner import plan_actions
from backend.services.orchestrator import run_ai_agent
from backend.ai.planner import create_plan
from backend.ai.executor import execute_plan, execute_approved
from backend.ai.remediator import sign_actions
from backend.ai.audit import get_recent_logs

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
    answer: str


class PlanRequest(BaseModel):
    message: str


class PlanResponse(BaseModel):
    steps: list[dict]


class AgentRequest(BaseModel):
    message: str


class AgentResponse(BaseModel):
    steps: list[dict]
    final_answer: str


class ApproveRequest(BaseModel):
    actions: list[dict]


class ApproveResponse(BaseModel):
    steps: list[dict]


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
      1. planner  — convert user message into ordered AWS CLI steps
      2. executor — run each step, collect sanitized results
      3. formatter — correlate all results into a unified analysis
    """
    message = request.message.strip()
    _log("INFO", f"Received message: {message}")

    # Step 1 — Plan
    try:
        plan = create_plan(message)
        _log("INFO", f"Plan created: {len(plan)} steps")
    except Exception as e:
        _log("ERROR", f"Planner failed: {e}")
        return ChatResponse(answer=f"Gagal membuat rencana eksekusi: {str(e)}")

    # Step 2 — Execute
    try:
        results = execute_plan(plan)
        success_count = sum(1 for s in results["steps"] if s["success"])
        _log("INFO", f"Executed {len(results['steps'])} steps, {success_count} succeeded")
    except Exception as e:
        _log("ERROR", f"Executor failed: {e}")
        return ChatResponse(answer=f"Gagal mengeksekusi perintah: {str(e)}")

    # Step 3 — Format
    try:
        answer = formatter.format_steps(results["steps"])
        _log("INFO", "Response formatted successfully")
    except Exception as e:
        _log("ERROR", f"Formatter failed: {e}")
        # Fallback: return raw step results
        fallback = "\n".join(
            f"Step {s['step']}: {s['command']}\n{s['result']}"
            for s in results["steps"]
        )
        answer = fallback

    return ChatResponse(answer=answer)

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


@app.post("/ai/approve", response_model=ApproveResponse)
def approve(request: ApproveRequest):
    """
    Execute pre-approved remediation actions.
    Only called when user explicitly confirms with "approve".
    Each action is re-validated against safe_commands before execution.
    """
    _log("INFO", f"Approval received for {len(request.actions)} actions")

    try:
        result = execute_approved(request.actions)
        _log("INFO", f"Approved execution completed: {len(result['steps'])} steps")
        return ApproveResponse(steps=result["steps"])
    except Exception as e:
        _log("ERROR", f"Approved execution failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/ai/audit")
def audit_log(n: int = 50):
    """Return the last N audit log entries."""
    _log("INFO", f"Audit log requested (last {n} entries)")
    return {"entries": get_recent_logs(n)}
