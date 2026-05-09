# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A chat UI that visualises AI agent pipelines in real time — showing tool calls, thinking traces, and agent handoffs as they stream. Intended as a frontend for the Ericsson SOX multi-agent backend (see parent repo CLAUDE.md), but ships with a fully self-contained demo mode that requires no credentials.

## Dev Setup & Running

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Open http://localhost:8000
```

The FastAPI server serves both the API (`/api/chat`, `/health`) and the static frontend (`index.html`). No build step — the frontend is a single HTML file.

## Connecting to a Live Backend

```bash
cp backend/.env.example backend/.env
# Fill in EKX_API_URL, EKX_API_KEY, set LIVE_MODE=true
```

Toggle between demo and live mode via the header button in the UI.

## Architecture

**Two-file project:**
- `index.html` — entire frontend (vanilla JS, no framework, no build). CSS variables drive the design system. All agent event rendering lives in the JS at the bottom.
- `backend/main.py` — FastAPI app with two streaming generators: `demo_stream` (scripted scenarios, no credentials) and `live_stream` (proxies to EKX API).

**SSE event contract** — the only interface between frontend and backend:

| Type | Fields |
|---|---|
| `agent` | `name`, `content` |
| `thinking` | `content` |
| `tool_call` | `tool`, `input` |
| `tool_result` | `tool`, `content` |
| `text_delta` | `content` |
| `done` | — |
| `error` | `message` |

**Demo mode** — `scenarioFor()` in `index.html` routes queries to one of four scripted scenarios (research/analysis/code/general) based on keyword regex. Each scenario defines a sequence of timed steps and a canned reply. `demo_stream` in `main.py` is the server-side equivalent used when `liveMode=false` in the frontend (routes via `/api/chat`).

**Live mode** — `live_stream` in `main.py` proxies POST requests to `EKX_API_URL`, parses the SSE response, and maps raw EKX event shapes to the standard schema via `_map_ekx_event()`. The mapping is a best-guess stub — update it once you inspect actual EKX network traffic.
