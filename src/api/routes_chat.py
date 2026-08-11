"""Dashboard assistant — a Claude-backed chat so a visitor who doesn't
understand a panel can just ask.

Design decisions baked in here:
  * The API key lives ONLY on the server (env ANTHROPIC_API_KEY). The browser
    never sees it — the frontend talks to this endpoint, this endpoint talks
    to Anthropic.
  * It answers dashboard + general flood/weather questions, but a hard
    life-safety guardrail (in the system prompt) forbids it from telling any
    individual to evacuate or stay — those calls belong to NWS + the county
    EOC + 911, and it must say so.
  * It is LIVE-AWARE: today's real alert level and forecast numbers are read
    off disk and injected so it can answer "why is it GREEN right now?".
  * Simple per-IP rate limit bounds cost on a public site.

Uses httpx (already a dependency) against the Anthropic Messages API directly
rather than adding the SDK.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["Assistant"])

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# Haiku: cheap + fast, plenty for an explainer. Override with AFFI_CHAT_MODEL.
MODEL = os.environ.get("AFFI_CHAT_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 700

# --- per-IP rate limit (per process; fine for a single-container pilot) ---
_RATE_MAX = int(os.environ.get("AFFI_CHAT_RATE_PER_MIN", "15"))
_hits: dict[str, deque] = defaultdict(deque)


def _rate_ok(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= _RATE_MAX:
        return False
    q.append(now)
    return True


# --- grounding: who the assistant is + what it may/may not do ---
_SYSTEM = """\
You are the assistant for FloodAI (AFFI) — an AI flood early-warning dashboard \
for the Upper Sonoita Creek watershed (HUC-12 150503010204) near Patagonia, \
Santa Cruz County, Arizona. Your job is to help a visitor understand the \
dashboard and flood/weather concepts in plain, calm language.

HOW THE SYSTEM WORKS (so you can explain any panel):
- Six stages: (1) Meteorology — a 31-member GFS ensemble rainfall forecast \
averaged over the watershed (Mean Areal Precipitation). (2) Hydrology — a \
two-part "hurdle model": an LSTM gate decides IF today is a flood day, then \
XGBoost estimates HOW BIG the peak discharge is. Trained first on the \
data-rich Babocomari River gauge, then adapted to Sonoita Creek (USGS \
09481500). (3) Hydraulics — today's discharge is looked up in a flood-map \
library built from real FEMA floodplain + FEMA base flood elevations minus \
USGS 3DEP lidar terrain, giving depth = water-surface minus ground. (4) \
Probabilistic — best/likely/worst (P10/P50/P90) maps + a probability layer. \
(5) Benchmarking — every event is classified by return period (2–500 year) \
against NOAA Atlas 14 + USGS statistics. (6) Alert — GREEN / ADVISORY / \
WATCH / WARNING, shown to government EOC staff only.
- Alert ladder: GREEN (normal) < ADVISORY < WATCH < WARNING.
- Return period: a "25-year flood" has ~1-in-25 (4%) chance in any year; it \
is NOT a countdown. Discharge = water volume per second (cfs). P90 = the \
pessimistic (~10% chance worse) scenario; road-closure/evac calls default to \
it. Life-safety threshold = water 0.5 m (~1.6 ft) deep, enough to sweep an \
adult off their feet or float a car. The gauge pin uses the Google-Flood-Hub \
scale: Normal / Warning / Danger / Extreme.

HONESTY (never oversell):
- This is a model, not certainty. Event DETECTION is strong (AUC-ROC ~0.96); \
exact flood SIZE is harder in flashy desert streams (NSE ~0.35), so treat \
magnitude as a wide band. If our forecast and the National Weather Service \
disagree, say the NWS is authoritative.

HARD SAFETY RULE — never break this:
- You must NOT tell any individual whether to evacuate, stay, drive, or shelter. \
If someone asks "should I leave / is my house safe / is this road safe", do \
NOT decide for them. Explain what the dashboard shows, then tell them \
life-safety decisions come from the National Weather Service, their county \
Emergency Operations Center, and 911 — and to call 911 if they are in danger \
now. Never say "you are safe."

STYLE: concise, plain language, no jargon without a one-line explanation. \
You may answer general flood/weather questions too, but stay honest about \
uncertainty. If a question is unrelated to floods/weather/this dashboard, \
gently steer back.\
"""


def _live_context() -> str:
    """Today's real alert + forecast, read off disk, so the assistant can
    answer questions about the current situation. Best-effort — returns a
    short note if the files aren't present."""
    lines: list[str] = []
    try:
        pkt = json.loads((OUTPUTS / "task1_alert_packet.json").read_text())
        lines.append(f"Current alert level: {pkt.get('current_alert')}. "
                     f"Worst level in next 7 days: {pkt.get('max_7day_alert')}. "
                     f"Data source: {pkt.get('data_source')}, generated {pkt.get('generated_utc')}.")
    except Exception:
        pass
    try:
        fc = json.loads((OUTPUTS / "task4" / "forecast_7day.json").read_text())
        today = fc.get("today", {})
        rain = today.get("rainfall_inches", {})
        q = today.get("discharge_cms", {})
        lines.append(
            f"Today ({today.get('date')}): forecast rainfall p50 {rain.get('p50')} in "
            f"(range {rain.get('p10')}–{rain.get('p90')} in); "
            f"peak discharge p50 {round(q.get('p50', 0), 1)} cms, worst-case p90 {round(q.get('p90', 0), 1)} cms."
        )
    except Exception:
        pass
    if not lines:
        return "Live forecast data is not available to you right now; answer generally and say so if asked about today."
    return "CURRENT LIVE SITUATION (real data, use it for 'right now' questions):\n" + "\n".join(lines)


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="Too many messages — please wait a minute and try again.")

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AFFI_ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="The assistant isn't configured yet — set ANTHROPIC_API_KEY on the server.",
        )

    if not req.messages:
        raise HTTPException(status_code=400, detail="No message provided.")

    # Cap history + per-message length to bound cost / prompt-injection surface.
    history = [
        {"role": m.role, "content": m.content[:4000]}
        for m in req.messages[-12:]
    ]

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM + "\n\n" + _live_context(),
        "messages": history,
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response is not None else str(e)
        raise HTTPException(status_code=502, detail=f"Assistant provider error: {detail}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the assistant: {e}")

    data = resp.json()
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    reply = "".join(parts).strip() or "Sorry — I couldn't produce an answer just now."
    return {"reply": reply, "model": MODEL}
