# Agent Chat

A chat interface that shows AI agents working in real time — tool calls, reasoning traces, and agent handoffs streamed live as they happen.

## Running it

**1. Install dependencies**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Start the server**

```bash
uvicorn main:app --reload --port 8000
```

**3. Open the app**

Go to [http://localhost:8000](http://localhost:8000)

The server serves both the API and the frontend, so no separate step needed.

---

## Demo vs Live mode

The app starts in **demo mode** — a scripted agent pipeline runs locally with no backend credentials needed. Click the chips on the welcome screen or type anything to try it.

Switch to **live mode** using the toggle in the header. This routes requests to your real backend (see below).

---

## Connecting to EKX

**1. Copy the env file**

```bash
cp backend/.env.example backend/.env
```

**2. Fill in your credentials**

```
EKX_API_URL=https://ekx.cloud.sap/api/v1/chat   # check the actual endpoint
EKX_API_KEY=your-key-here
LIVE_MODE=true
```

> **Tip:** To find the exact API URL and event format, open DevTools in EKX (`ekx.cloud.sap`), go to the **Network** tab, send a message, and inspect the streaming request — look at the EventStream tab for the JSON shapes.

**3. Map the event format**

Update the `_map_ekx_event()` function in `backend/main.py` to match whatever EKX actually sends. The frontend expects these event types:

| Event | Fields |
|---|---|
| `agent` | `name`, `content` |
| `thinking` | `content` |
| `tool_call` | `tool`, `input` |
| `tool_result` | `tool`, `content` |
| `text_delta` | `content` |
| `done` | — |
| `error` | `message` |

**4. Restart the server** and toggle to **live** in the header.

---

## Project structure

```
agent-chat/
  index.html        — frontend (single file, no build step)
  backend/
    main.py         — FastAPI server
    requirements.txt
    .env.example
```
