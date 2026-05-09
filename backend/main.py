"""
Agent Chat — FastAPI streaming backend
---------------------------------------
Proxies SSE requests to the sox-pipeline CF app.

Requires SOX_PIPELINE_URL in .env.

Run:
    cd backend
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import pathlib

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import AsyncGenerator

load_dotenv()

SOX_PIPELINE_URL = os.getenv("SOX_PIPELINE_URL", "").rstrip("/")

app = FastAPI(title="Ericsson SOX Agent Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def pipeline_stream(message: str) -> AsyncGenerator[str, None]:
    if not SOX_PIPELINE_URL:
        yield sse({"type": "error", "message": "SOX_PIPELINE_URL not set — check .env"})
        return

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{SOX_PIPELINE_URL}/analyze",
                json={"message": message},
                headers={"Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
    except httpx.HTTPStatusError as exc:
        yield sse({"type": "error", "message": f"Pipeline error {exc.response.status_code}"})
    except Exception as exc:
        yield sse({"type": "error", "message": str(exc)})


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        pipeline_stream(req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "pipeline_url": SOX_PIPELINE_URL}


# ── Serve frontend ─────────────────────────────────────────────────────────
_STATIC = pathlib.Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
