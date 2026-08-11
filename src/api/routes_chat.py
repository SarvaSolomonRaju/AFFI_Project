"""Dashboard assistant — a free, offline knowledge assistant.

No paid API and no external model: it answers from a curated knowledge base
about this dashboard plus today's live numbers read off disk. That means it
costs nothing to run, works without internet, and can never hallucinate a
wrong "fact" the way a general LLM might — every answer is written and
grounded. It matches a visitor's question to the best topic by keyword/phrase
scoring, handles a few hard intents (live status, life-safety deflection,
greetings), and falls back to a menu of what it can explain.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["Assistant"])

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"


# --------------------------------------------------------------------------
# Live data — so "what's the alert right now?" gets a real answer.
# --------------------------------------------------------------------------
def _live() -> dict:
    out: dict = {}
    try:
        pkt = json.loads((OUTPUTS / "task1_alert_packet.json").read_text())
        out["alert"] = pkt.get("current_alert")
        out["max7"] = pkt.get("max_7day_alert")
    except Exception:
        pass
    try:
        fc = json.loads((OUTPUTS / "task4" / "forecast_7day.json").read_text())
        t = fc.get("today", {})
        out["date"] = t.get("date")
        out["rain"] = t.get("rainfall_inches", {})
        out["q"] = t.get("discharge_cms", {})
    except Exception:
        pass
    return out


def _live_status_answer() -> str:
    d = _live()
    if not d.get("alert"):
        return ("I can't read today's live forecast right now. In general the alert level is "
                "GREEN (normal), ADVISORY, WATCH, or WARNING, escalating in that order.")
    alert = d["alert"]
    meaning = {
        "GREEN": "normal operations — no flooding expected",
        "ADVISORY": "stay alert — minor or nuisance flooding is possible",
        "WATCH": "prepare — conditions could produce significant flooding",
        "WARNING": "act now — dangerous flooding is expected or happening",
    }.get(alert, "")
    parts = [f"Right now the alert level is **{alert}** — {meaning}."]
    if d.get("max7") and d["max7"] != alert:
        parts.append(f"The worst level expected in the next 7 days is {d['max7']}.")
    rain = d.get("rain") or {}
    q = d.get("q") or {}
    if rain.get("p50") is not None:
        parts.append(f"Today's most-likely rainfall is about {rain['p50']} in "
                     f"(worst-case {rain.get('p90')} in).")
    if q.get("p50") is not None:
        parts.append(f"Forecast peak flow is ~{round(q['p50'], 1)} m³/s "
                     f"(worst-case ~{round(q.get('p90', 0), 1)} m³/s).")
    parts.append("Remember this is a model — the National Weather Service is the authoritative source.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Knowledge base. Each entry: trigger keywords/phrases + a written answer.
# --------------------------------------------------------------------------
KB: list[dict] = [
    {"k": ["what is affi", "what is this", "what is floodai", "what does this do", "about this", "what is the dashboard", "purpose"],
     "a": "This is FloodAI (AFFI) — an AI flood early-warning dashboard for the Upper Sonoita Creek watershed near Patagonia, Arizona. It turns a weather forecast into a flood map for emergency managers in about a minute, so they can see where flooding is likely and act before the water arrives. It combines real weather forecasts, an AI hydrology model, and federal flood-mapping data."},

    {"k": ["alert level mean", "green mean", "advisory mean", "watch mean", "warning mean", "what do the alert", "alert ladder", "alert colors", "what are the alert levels"],
     "a": "There are four escalating levels: GREEN (normal, no flooding expected) → ADVISORY (stay alert, minor flooding possible) → WATCH (prepare, significant flooding could occur) → WARNING (act now, dangerous flooding expected). The color and word both rise with the threat."},

    {"k": ["right now", "current alert", "alert now", "today", "current status", "what is the alert", "whats the alert", "why is it green", "why is it advisory", "why is it watch", "why is it warning", "current situation", "current level"],
     "a": "__LIVE__"},

    {"k": ["return period", "25 year", "100 year", "2 year", "how rare", "recurrence interval", "year flood", "year event"],
     "a": "A 'return period' is how rare a flood is. A '25-year flood' has about a 1-in-25 (4%) chance of happening in any given year — it is NOT a countdown, and two can happen close together. It's just a standard way engineers and FEMA describe severity."},

    {"k": ["discharge", "cfs", "cms", "flow rate", "cubic feet", "cubic metres", "how much water"],
     "a": "Discharge is how much water is moving down the channel, measured as volume per second — cubic feet per second (cfs) or cubic metres per second (m³/s). The bigger the discharge, the bigger and deeper the flood."},

    {"k": ["p90", "p50", "p10", "best case", "worst case", "likely case", "percentile", "three scenarios", "best likely worst"],
     "a": "A forecast is never a single certain number, so the dashboard shows three scenarios: BEST (P10, optimistic — little water), LIKELY (P50, the best single estimate), and WORST (P90, pessimistic — only about a 1-in-10 chance the real flood is worse). Road-closure and evacuation decisions default to the worst case, to stay on the safe side."},

    {"k": ["life safety", "life-safety", "0.5", "0.5m", "1.6 ft", "sweep", "how deep is dangerous", "life safety threshold"],
     "a": "The life-safety threshold is water about 0.5 m (1.6 ft) deep — enough to sweep an adult off their feet or float a car. The 'life-safety risk' number is the chance any spot in the area gets at least this deep today."},

    {"k": ["probability", "poi", "heatmap", "chance of water", "inundation probability", "probability layer"],
     "a": "The flood-probability heatmap shows the chance (0–100%) that each spot gets any flood water today, given the forecast's uncertainty. Darker/warmer = higher chance. It's the same idea as Google Flood Hub's 'Inundation Probability' layer."},

    {"k": ["how often", "frequency", "inundation history", "recurrence layer", "how often does it flood"],
     "a": "The 'how often it floods' layer colors the map by how frequently each spot floods: deep red = it floods in a common (2-year) storm, pale yellow = only in a rare (500-year) one. It's built from the flood-map library — the analog of Google Flood Hub's inundation-history layer."},

    {"k": ["gauge", "gauge pin", "normal warning danger extreme", "pin on the map", "gauge status", "river gauge"],
     "a": "The pin on the creek is a live gauge status marker. It reads today's forecast flow against the flood thresholds and colors itself Normal / Warning / Danger / Extreme — the same scale Google Flood Hub uses. Green means flow is in the channel; it turns amber, orange, then red as flooding gets worse. Click it for details."},

    {"k": ["time to peak", "time to act", "how long", "how much time", "when will it peak", "peak"],
     "a": "'Time to act' (time-to-peak) is roughly how long until the flood reaches its highest point — i.e. how much time you have before it's at its worst. It's estimated from the watershed's size and slope using standard hydrology formulas."},

    {"k": ["people at risk", "population", "how many people", "exposure", "population at risk"],
     "a": "'People at risk' estimates how many people are in areas that could get life-threatening depth in the worst-case scenario, using WorldPop population data. It's an estimate of exposure, to help prioritize warnings and resources."},

    {"k": ["map", "layers", "what can i see on the map", "map layers", "fema zone", "flood zone"],
     "a": "The map shows: the official FEMA flood zone (a fixed legal boundary, red), today's forecast flood depth, a flood-probability heatmap, a 'how often it floods' layer, evacuation routes colored by whether today's flood cuts them off, roads and buildings colored by flood severity, critical facilities, and a live gauge pin. Toggle layers in the 'Layers' panel and read the colors in the 'Legend'."},

    {"k": ["evacuation route", "evac route", "escape route", "cut off", "road closed", "which roads"],
     "a": "Evacuation routes are colored against today's forecast: green = CLEAR (usable now), amber = passable with caution, red = CUT OFF (do not use). Click a route to see the water depth across it. This helps a manager see which escape routes are still open."},

    {"k": ["how does the model work", "how does the ai work", "hurdle model", "lstm", "xgboost", "how does it predict", "the ai", "machine learning", "neural network"],
     "a": "The AI hydrology stage is a two-part 'hurdle model': first an LSTM neural network reads the recent rainfall pattern and decides IF today is a flood day; only if it fires does an XGBoost model estimate HOW BIG the flood is. This split matches desert streams — dry ~95% of the time, occasionally violent — and is why the system detects flood events reliably even when exact size is hard."},

    {"k": ["accurate", "accuracy", "reliable", "can i trust", "how good", "nse", "how reliable", "confidence"],
     "a": "Honestly: the model is strong at DETECTING whether a flood will happen (about 96% accurate at ranking flood vs. non-flood days), but exact flood SIZE is harder in flashy desert streams (a lower NSE score), so magnitude is treated as a wide band, not an exact number. That's why decisions lean on detection and default to the worst-case scenario. When our forecast and the National Weather Service disagree, trust the NWS."},

    {"k": ["training", "trained", "babocomari", "transfer learning", "how was it trained", "anchor"],
     "a": "The model is trained in two stages: first on the data-rich Babocomari River gauge record to learn general desert flash-flood behavior, then fine-tuned on Sonoita Creek's own gauge (USGS 09481500). This 'transfer learning' is what lets it work in a watershed without decades of its own data."},

    {"k": ["flood library", "hec-ras", "hec ras", "how is depth", "depth computed", "how do you know the depth", "hydraulics"],
     "a": "Flood depth is a subtraction: depth = water-surface elevation minus ground elevation. The dashboard uses a pre-built library of depth maps made from real FEMA floodplain data, FEMA base flood elevations, and USGS lidar terrain — so every depth traces to an official federal source, not a black box."},

    {"k": ["simulation", "what if", "sim mode", "slider", "simulation mode", "explore"],
     "a": "Simulation mode lets you explore 'what-if' scenarios: slide the rainfall bar and every panel updates to show what would happen at that rainfall level. It's not a real forecast — it's a planning and training tool. Live Forecast mode shows today's real situation."},

    {"k": ["who is this for", "audience", "who uses", "public", "emergency manager", "who sees this"],
     "a": "It's built for authorized government emergency personnel — county emergency managers, public-works directors, and EOC staff — to support decisions like closing roads and evacuating. Alerts are not broadcast directly to the public; that stays a decision for responsible officials."},

    {"k": ["data source", "where does the data", "what data", "sources", "where do the numbers"],
     "a": "All data is free and public from federal agencies: NOAA GFS weather forecasts, USGS stream gauges and lidar terrain, FEMA flood maps and base flood elevations, NOAA Atlas 14 rainfall statistics, and WorldPop population. No paid or private data."},

    {"k": ["decision cockpit", "cockpit"],
     "a": "The Decision Cockpit gathers the time-sensitive decision numbers in one place: time-to-peak (how long you have), the life-safety probability, forecast uncertainty, and a plain-English 'what to do' posture (Monitor / Prepare / Deploy / Execute) matched to the threat."},

    {"k": ["bulletin"],
     "a": "The bulletin generator writes an NWS-style WHAT / WHERE / WHEN / IMPACTS statement you can copy and relay, including the legal basis for road-closure barricades (Arizona's 'Stupid Motorist Law', ARS 28-910)."},

    {"k": ["nws", "national weather service", "official", "difference between", "your alert vs", "who is right"],
     "a": "The 'Official — National Weather Service' panel shows the government's real, authoritative alerts. Our forecast below it is a model. When the two disagree, always trust the NWS and your county EOC — that's stated on the panel itself."},

    {"k": ["7 day", "seven day", "outlook", "forecast ahead", "next week", "7-day"],
     "a": "The 7-day outlook shows the forecast alert level and likely/worst flood for each of the next seven days, so you can pre-position resources days ahead. Confidence is lower further out (2–7 days) and highest in the final hours (0–6 hours)."},

    {"k": ["historical", "past event", "comparison", "history", "past floods"],
     "a": "The historical comparison replays documented past Sonoita Creek flood events through the same pipeline, so you can see how today's forecast compares to real floods the community has experienced."},
]

SAFETY_TRIGGERS = ["should i evacuate", "should i leave", "is my house", "am i safe", "is it safe",
                   "should i stay", "is this road safe", "can i drive", "should i drive", "my home",
                   "shelter", "rescue me", "help me", "in danger", "trapped"]
SAFETY_ANSWER = ("I can't make a personal safety decision for you — and I won't guess with something "
                 "this important. For whether to evacuate, stay, or travel, follow the National Weather "
                 "Service, your county Emergency Operations Center, and local officials. **If you are in "
                 "danger right now, call 911.** What I can do is explain what any part of this dashboard "
                 "means.")

GREET_TRIGGERS = ["hello", "hi", "hey", "good morning", "good afternoon", "yo "]
THANKS_TRIGGERS = ["thank", "thanks", "cheers", "appreciate"]

TOPIC_MENU = ("I can explain anything on this dashboard in plain language. Try asking about: the current "
              "alert level, what a return period is, the flood-probability or 'how often it floods' map "
              "layers, the gauge pin, time-to-peak, how the AI model works, how accurate it is, evacuation "
              "routes, or simulation mode. What would you like to understand?")


def _tokens(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _answer(question: str) -> str:
    q = _tokens(question)
    qc = " " + q + " "

    # 1) Life-safety questions get deflected, always, before anything else.
    if any(t in q for t in SAFETY_TRIGGERS):
        return SAFETY_ANSWER

    # 2) Greetings / thanks (only if short and no real topic keywords).
    if len(q.split()) <= 4:
        if any(f" {t}" in qc or q.startswith(t) for t in GREET_TRIGGERS):
            return "Hi! " + TOPIC_MENU
        if any(t in q for t in THANKS_TRIGGERS):
            return "You're welcome — ask me anything else about the dashboard any time."

    # 3) Best knowledge-base match by keyword/phrase overlap.
    best, best_score = None, 0.0
    for entry in KB:
        score = 0.0
        for kw in entry["k"]:
            if kw in q:
                # multi-word phrase match is a strong signal
                score += 2.0 + 0.5 * kw.count(" ")
        if score > best_score:
            best, best_score = entry, score

    if best and best_score >= 2.0:
        return _live_status_answer() if best["a"] == "__LIVE__" else best["a"]

    # 4) Nothing matched well.
    return ("I'm not sure I caught that. " + TOPIC_MENU)


# --------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="No question provided.")
    reply = _answer(user_msgs[-1].content[:2000])
    return {"reply": reply, "source": "local-knowledge-base"}
