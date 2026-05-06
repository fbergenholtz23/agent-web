"""
Agent Chat — FastAPI streaming backend
--------------------------------------
Demo mode (default): streams synthetic agent events so the frontend
works without any credentials.

Live mode: set LIVE_MODE=true in .env and fill in EKX_API_URL /
EKX_API_KEY. The `live_stream` function below is where you wire up
the real EKX API once you have the endpoint spec.

Run:
    cd backend
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

EKX_API_URL = os.getenv("EKX_API_URL", "")
EKX_API_KEY  = os.getenv("EKX_API_KEY", "")
LIVE_MODE    = os.getenv("LIVE_MODE", "false").lower() == "true"

app = FastAPI(title="Agent Chat API")

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


# ── Standard event schema ──────────────────────────────────────────────────
#
# The frontend understands exactly these event types:
#
#   {"type": "agent",       "name": "<str>",  "content": "<str>"}
#   {"type": "thinking",    "content": "<str>"}
#   {"type": "tool_call",   "tool": "<str>",  "input": "<str>"}
#   {"type": "tool_result", "tool": "<str>",  "content": "<str>"}
#   {"type": "text_delta",  "content": "<str>"}   ← stream reply char-by-char or in chunks
#   {"type": "done"}
#   {"type": "error",       "message": "<str>"}


# ── Demo pipeline ──────────────────────────────────────────────────────────

RESEARCH_STEPS: list[dict] = [
    {"delay": 0.38, "type": "agent",       "name": "orchestrator", "content": "Routing to research pipeline…"},
    {"delay": 0.75, "type": "thinking",    "content": "Query requires factual retrieval. Dispatching web search then synthesising findings."},
    {"delay": 0.50, "type": "tool_call",   "tool": "web_search",   "use_query": True},
    {"delay": 1.30, "type": "tool_result", "tool": "web_search",   "content": "Retrieved 7 sources. Extracting passages from top results."},
    {"delay": 0.85, "type": "agent",       "name": "researcher",   "content": "Ranking sources and extracting key claims…"},
    {"delay": 1.05, "type": "thinking",    "content": "Top 4 sources agree. One outlier — will flag as contested."},
    {"delay": 0.45, "type": "tool_call",   "tool": "extract_content", "input": "primary-source.example/article"},
    {"delay": 0.90, "type": "tool_result", "tool": "extract_content", "content": "Extracted 1,180 tokens. Confidence: high."},
    {"delay": 0.60, "type": "agent",       "name": "synthesizer",  "content": "Composing final response…"},
]

ANALYSIS_STEPS: list[dict] = [
    {"delay": 0.36, "type": "agent",       "name": "orchestrator", "content": "Dispatching comparative analysis pipeline…"},
    {"delay": 0.82, "type": "thinking",    "content": "Structured comparison task. Building evaluation matrix across key dimensions."},
    {"delay": 0.70, "type": "agent",       "name": "analyst",      "content": "Building evaluation framework across 7 dimensions…"},
    {"delay": 0.48, "type": "tool_call",   "tool": "structured_eval", "input": "performance, dx, ecosystem, scalability, maturity"},
    {"delay": 1.10, "type": "tool_result", "tool": "structured_eval", "content": "Matrix complete. Clear winner on 3 dimensions, contested on 4."},
    {"delay": 1.20, "type": "thinking",    "content": "Neither option dominates outright. Context of use determines the right call."},
    {"delay": 0.80, "type": "agent",       "name": "validator",    "content": "Cross-checking claims against benchmark data…"},
    {"delay": 0.55, "type": "agent",       "name": "synthesizer",  "content": "Formatting recommendation with caveats…"},
]

CODE_STEPS: list[dict] = [
    {"delay": 0.35, "type": "agent",       "name": "orchestrator", "content": "Routing to code generation pipeline…"},
    {"delay": 0.75, "type": "thinking",    "content": "Code task. Plan: analyse requirements → generate typed implementation → review for edge cases."},
    {"delay": 0.90, "type": "agent",       "name": "coder",        "content": "Analysing requirements and generating implementation…"},
    {"delay": 0.46, "type": "tool_call",   "tool": "code_sandbox", "input": "validate_runtime: python@3.11"},
    {"delay": 0.80, "type": "tool_result", "tool": "code_sandbox", "content": "Runtime validated. Type annotations and modern syntax available."},
    {"delay": 1.10, "type": "thinking",    "content": "Two variants: safe (returns None) and strict (raises). Adding guard clause for empty input."},
    {"delay": 0.85, "type": "agent",       "name": "reviewer",     "content": "Checking correctness, edge cases, and idiomatic style…"},
    {"delay": 0.50, "type": "agent",       "name": "synthesizer",  "content": "Adding usage examples and final polish…"},
]

RESEARCH_REPLY = """\
Based on my research across several sources, here's a clear breakdown:

**Core mechanism**
At its heart, the system decomposes the problem space into discrete units — each handled by a \
specialised process operating in parallel or in sequence, depending on dependencies.

**Why it matters**
This design dramatically improves throughput and failure isolation. When one unit fails, the rest \
continue unaffected, and recovery is localised rather than systemic.

**Current frontier**
Active research is focused on reducing coordination overhead and making these systems more \
observable. That second part is what tooling like this is built to address.

Is there a specific layer — architecture, implementation, or theory — you'd like to go deeper on?"""

ANALYSIS_REPLY = """\
Here's a structured comparison:

**Performance**
Option A edges ahead in raw throughput. Option B recovers faster from spikes — at p99 latency, B often wins.

**Developer Experience**
Option B is the clear winner: faster onboarding, excellent tooling, more intuitive abstractions.

**Ecosystem & Longevity**
Option A has a larger, more mature ecosystem. Option B has stronger momentum in greenfield projects.

---

**Recommendation:**
- New project, fast iteration, small team → **Option B**
- Existing infrastructure, extreme scale → **Option A**

What does your current setup look like? That'll sharpen this."""

CODE_REPLY = """\
Here's a clean, typed implementation:

```python
from __future__ import annotations
from typing import Any
import json


def parse_json_safe(raw: str) -> dict[str, Any] | None:
    \"\"\"Parse JSON, returning None on any failure.\"\"\"
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def parse_json_strict(raw: str) -> dict[str, Any]:
    \"\"\"Parse JSON, raising ValueError with a clean message on failure.\"\"\"
    if not raw or not raw.strip():
        raise ValueError("Input is empty or whitespace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at position {exc.pos}: {exc.msg}") from exc
```

**`_safe`** — use when bad input is expected and handled at the call site.
**`_strict`** — use when bad input is a programming error that should surface loudly.

Need me to add nested key extraction or a streaming parser variant?"""


def _pick(message: str) -> tuple[list[dict], str]:
    m = message.lower()
    if any(k in m for k in ("code","write","build","create","implement","function","python","script","class")):
        return CODE_STEPS, CODE_REPLY
    if any(k in m for k in ("analyz","compar","vs ","versus","pros","cons","tradeoff","evaluat")):
        return ANALYSIS_STEPS, ANALYSIS_REPLY
    return RESEARCH_STEPS, RESEARCH_REPLY


async def demo_stream(message: str) -> AsyncGenerator[str, None]:
    steps, reply = _pick(message)

    for step in steps:
        await asyncio.sleep(step["delay"])
        payload = {k: v for k, v in step.items() if k not in ("delay", "use_query")}
        if step.get("use_query"):
            payload["input"] = message if len(message) <= 60 else message[:60] + "…"
        yield sse(payload)

    for ch in reply:
        yield sse({"type": "text_delta", "content": ch})
        await asyncio.sleep(0.009)

    yield sse({"type": "done"})


# ── Live EKX stream ────────────────────────────────────────────────────────

async def live_stream(message: str) -> AsyncGenerator[str, None]:
    """
    Wire up the EKX API here.

    From the UI at ekx.cloud.sap the backend is likely:
      POST https://ekx.cloud.sap/api/v1/chat  (or similar)
    with SSE streaming and JSON events.

    Steps to complete this:
    1. Open the network tab in DevTools while using EKX, send a message,
       and inspect the streaming response to see the exact event format.
    2. Fill in EKX_API_URL and EKX_API_KEY in .env
    3. Update `_map_ekx_event` below to match the real event shapes.
    4. Set LIVE_MODE=true and restart.
    """
    if not EKX_API_URL:
        yield sse({"type": "error", "message": "EKX_API_URL not set — check .env"})
        return

    headers = {
        "Authorization": f"Bearer {EKX_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {
        "message": message,
        # add EKX-specific fields once you have the spec, e.g.:
        # "conversation_id": "...",
        # "model": "...",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", EKX_API_URL, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw_text = line[5:].strip()
                    if raw_text in ("[DONE]", ""):
                        break
                    try:
                        raw = json.loads(raw_text)
                    except json.JSONDecodeError:
                        continue
                    mapped = _map_ekx_event(raw)
                    if mapped:
                        yield sse(mapped)

        yield sse({"type": "done"})

    except httpx.HTTPStatusError as exc:
        yield sse({"type": "error", "message": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"})
    except Exception as exc:
        yield sse({"type": "error", "message": str(exc)})


def _map_ekx_event(raw: dict) -> dict | None:
    """
    Translate a raw EKX SSE event into the standard frontend schema.

    This is a best-guess mapping — update it once you inspect the real
    event shapes from the EKX network traffic.
    """
    etype = raw.get("type") or raw.get("event") or ""

    # OpenAI-compatible streaming (common for SAP AI Core)
    if "choices" in raw:
        delta = raw["choices"][0].get("delta", {})
        if content := delta.get("content"):
            return {"type": "text_delta", "content": content}
        return None

    # EKX agent / step events (guessed — adjust to match real names)
    if etype in ("agent_step", "agent"):
        return {"type": "agent", "name": raw.get("agent", "agent"), "content": raw.get("message", raw.get("content", ""))}
    if etype in ("thinking", "reasoning", "thought"):
        return {"type": "thinking", "content": raw.get("content", raw.get("text", ""))}
    if etype == "tool_call":
        return {"type": "tool_call", "tool": raw.get("tool", "tool"), "input": str(raw.get("input", ""))}
    if etype == "tool_result":
        return {"type": "tool_result", "tool": raw.get("tool", "tool"), "content": str(raw.get("output", raw.get("content", "")))}
    if etype in ("text", "text_delta", "delta", "content"):
        return {"type": "text_delta", "content": raw.get("content", raw.get("text", ""))}
    if etype == "done":
        return {"type": "done"}
    if etype == "error":
        return {"type": "error", "message": raw.get("message", "Unknown error")}

    return None


# ── API ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    gen = live_stream(req.message) if LIVE_MODE else demo_stream(req.message)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": "live" if LIVE_MODE else "demo"}


# ── Serve frontend ─────────────────────────────────────────────────────────
# index.html lives one directory up from this file
_STATIC = pathlib.Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
