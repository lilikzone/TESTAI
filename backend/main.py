"""
AI Cloud Operator — Backend Entry Point
FastAPI server with Kiro orchestration
"""

from fastapi import FastAPI

app = FastAPI(
    title="AI Cloud Operator",
    description="Operate AWS using natural language powered by Gemini AI",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"status": "ok", "message": "AI Cloud Operator is running"}


@app.post("/api/execute")
def execute(query: str):
    # TODO: Route through guardrail → translator → AWS execution → formatter
    return {"query": query, "status": "not_implemented"}
