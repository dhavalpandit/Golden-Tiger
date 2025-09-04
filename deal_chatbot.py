from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import re

# ---------------------------
# Mock data (converted to Python)
# ---------------------------
mockLeadData = {
    "id": "gms-ashley-taylor",
    "lead": {
        "firstName": "Ashley",
        "lastName": "Taylor",
        "title": "Procurement Manager",
        "department": "Operations",
        "email": "ashley.taylor@gmsinc.com",
        "phone": "+1-404-555-0147",
        "location": "Atlanta, GA",
        "timezone": "ET",
        "avatarUrl": "/ashley-taylor.jpg",
        "status": "Lost",
        "stage": "Proposal",
        "estValue": 48500,
    },
    "company": {
        "name": "GMS Inc.",
        "website": "https://www.gms.com",
        "logoUrl": "/gms-inc-logo.jpg",
        "hq": "Tucker, GA",
        "industry": "Building Materials",
        "size": "1,000–5,000",
        "about": "GMS Inc. distributes specialty building materials and related products.",
    },
    "enrichment": {
        "education": ["B.S. Supply Chain, Georgia Tech"],
        "interests": ["On-time delivery", "Supplier consolidation"],
        "certs": ["APICS CSCP"],
        "disclaimer": "Demo enrichment from public sources",
    },
    "activity": [
        {
            "type": "email",
            "title": "Quote sent",
            "snippet": "Attached proposal for alt SKUs",
            "ts": "2025-09-02T15:30:00Z",
            "actor": "Jeffrey Dang",
        },
        {
            "type": "call",
            "title": "Call recap",
            "snippet": "Timeline risk flagged; needs 2-week ship",
            "ts": "2025-09-03T18:00:00Z",
            "actor": "Jeffrey Dang",
        },
        {
            "type": "email",
            "title": "Competitor notice",
            "snippet": "Incumbent can ship in 5 days",
            "ts": "2025-09-05T14:10:00Z",
            "actor": "Ashley Taylor",
        },
    ],
    "deal": {
        "products": ["Rebar #4", "Ready-mix Concrete 4000 PSI"],
        "competitors": ["IncumbentCo"],
        "expectedClose": "2025-09-15",
        "lostReasonPrimary": "Lead time / stock availability",
        "lostReasonSecondary": ["Delivery SLA", "Price sensitivity"],
        "evidenceLinks": [
            {"label": "Email thread", "href": "#"},
            {"label": "Proposal v2", "href": "#"},
        ],
        "salvagePlay": [
            "Offer alternates with 7-day ship from nearby DC",
            "Bundle delivery windows to reduce freight",
            "Add post-install support credit",
        ],
    },
    "insights": {
        "signals": ["Opened proposal 3×", "Visited alt SKU page", "Asked about freight"],
        "nextLikelyNeeds": ["Faster-ship alternate mix", "Freight-optimized bundle"],
        "confidence": 0.72,
    },
    "notes": [
        {"author": "Dhaval Pandit", "text": "Ashley prefers email over calls.", "ts": "2025-09-03T19:00:00Z"}
    ],
    "tasks": [
        {"title": "Draft recovery email", "due": "2025-09-08", "done": False},
        {"title": "Price review with Ops", "due": "2025-09-08", "done": False},
    ],
}

LEADS: Dict[str, Dict] = {
    mockLeadData["id"]: mockLeadData
}

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI(title="Deal Loss Chatbot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # tighten this for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Schemas
# ---------------------------
class ChatRequest(BaseModel):
    message: str
    leadId: str = "gms-ashley-taylor"  # default to your mock
    force_intent: Optional[str] = None  # optionally force an intent for testing

class ChatResponse(BaseModel):
    reply: str
    reasons: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    meta: Dict = Field(default_factory=dict)

# ---------------------------
# Helpers
# ---------------------------
def format_dt(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return ts

def classify_intent(msg: str) -> str:
    m = msg.lower()

    # direct why-lost
    if any(k in m for k in ["why", "reason", "lose", "lost", "lose the deal", "lost the business", "why did we"]):
        return "why_lost"

    # recovery
    if any(k in m for k in ["how recover", "salvage", "win back", "recover", "save deal", "get back"]):
        return "salvage"

    # timeline / evidence
    if any(k in m for k in ["timeline", "activity", "history", "what happened"]):
        return "timeline"
    if any(k in m for k in ["evidence", "proof", "show emails", "show notes"]):
        return "evidence"

    # loss drivers
    if any(k in m for k in ["price", "pricing", "cost", "freight", "delivery", "lead time", "sla", "stock"]):
        return "drivers"

    # summary
    if any(k in m for k in ["summary", "overview", "recap"]):
        return "summary"

    # coaching (improve conversation, scripts, objections)
    if any(k in m for k in [
        "improve conversation", "improve messaging", "coach", "coaching", "script",
        "email draft", "call script", "objection", "how to talk", "how can i improve"
    ]):
        return "coaching"

    # stakeholders (who to approach, involve)
    if any(k in m for k in [
        "stakeholder", "who to contact", "who should i contact", "decision maker",
        "approach the person", "involve", "org chart", "champion", "influencer"
    ]):
        return "stakeholders"

    # priority (what to do first, prioritize)
    if any(k in m for k in [
        "priority", "prioritize", "what to do first", "next best action", "nba",
        "what next", "rank tasks", "triage"
    ]):
        return "priority"

    return "general"

# ---------------------------
# Builders
# ---------------------------
def build_why_lost(lead: Dict) -> ChatResponse:
    deal = lead["deal"]
    activity = lead["activity"]

    reasons = [deal["lostReasonPrimary"]] + deal.get("lostReasonSecondary", [])
    ev = []
    for a in activity:
        if "timeline" in a["snippet"].lower() or "ship" in a["snippet"].lower() or "incumbent" in a["snippet"].lower():
            ev.append(f'{a["title"]} ({format_dt(a["ts"])}): {a["snippet"]}')

    reply_lines = [
        f"We lost **{lead['company']['name']}** primarily due to **{deal['lostReasonPrimary']}**.",
    ]
    if deal.get("lostReasonSecondary"):
        reply_lines.append("Contributing factors: " + ", ".join([f"**{r}**" for r in deal["lostReasonSecondary"]]) + ".")
    if ev:
        reply_lines.append("Supporting evidence:")
        for e in ev:
            reply_lines.append(f"• {e}")

    conf = lead.get("insights", {}).get("confidence", None)
    if conf is not None:
        reply_lines.append(f"Confidence in this assessment: **{int(conf*100)}%**.")

    next_steps = lead["deal"].get("salvagePlay", [])
    if next_steps:
        reply_lines.append("\nSuggested recovery plays:")
        for s in next_steps:
            reply_lines.append(f"• {s}")

    return ChatResponse(
        reply="\n".join(reply_lines),
        reasons=reasons,
        evidence=ev,
        next_steps=next_steps,
        meta={"stage": lead["lead"]["stage"], "status": lead["lead"]["status"]}
    )

def build_salvage(lead: Dict) -> ChatResponse:
    plays = lead["deal"].get("salvagePlay", [])
    signals = lead.get("insights", {}).get("signals", [])
    needs = lead.get("insights", {}).get("nextLikelyNeeds", [])

    reply = ["Here’s how we can try to recover the deal:"]
    for p in plays:
        reply.append(f"• {p}")
    if needs:
        reply.append("\nBased on behavior, likely needs:")
        for n in needs:
            reply.append(f"• {n}")
    if signals:
        reply.append("\nObserved signals:")
        for s in signals:
            reply.append(f"• {s}")

    return ChatResponse(
        reply="\n".join(reply),
        next_steps=plays,
        meta={"signals": signals, "nextLikelyNeeds": needs}
    )

def build_timeline(lead: Dict) -> ChatResponse:
    events = lead["activity"]
    lines = ["Key recent activity:"]
    ev = []
    for a in sorted(events, key=lambda x: x["ts"]):
        line = f"• {format_dt(a['ts'])} — {a['type'].upper()}: {a['title']} ({a['actor']}) — {a['snippet']}"
        lines.append(line)
        ev.append(line[2:])
    return ChatResponse(reply="\n".join(lines), evidence=ev)

def build_evidence(lead: Dict) -> ChatResponse:
    deal = lead["deal"]
    links = deal.get("evidenceLinks", [])
    lines = ["Evidence & references:"]
    ev = []
    for a in lead["activity"]:
        if any(k in a["snippet"].lower() for k in ["timeline", "ship", "incumbent", "freight", "sla"]):
            s = f"{a['title']}: {a['snippet']} ({format_dt(a['ts'])})"
            lines.append(f"• {s}")
            ev.append(s)
    if links:
        lines.append("\nFiles/links:")
        for l in links:
            lines.append(f"• {l['label']}: {l['href']}")
    return ChatResponse(reply="\n".join(lines), evidence=ev)

def build_drivers(lead: Dict) -> ChatResponse:
    reasons = {
        "Lead time / stock availability": 0,
        "Delivery SLA": 0,
        "Price sensitivity": 0,
        "Freight cost": 0,
        "Competitor advantage": 0,
    }
    reasons["Lead time / stock availability"] += 3 if lead["deal"]["lostReasonPrimary"].lower().startswith("lead time") else 0
    for r in lead["deal"].get("lostReasonSecondary", []):
        if "delivery" in r.lower():
            reasons["Delivery SLA"] += 2
        if "price" in r.lower():
            reasons["Price sensitivity"] += 2

    for a in lead["activity"]:
        s = a["snippet"].lower()
        if "needs 2-week ship" in s or "timeline" in s or "ship" in s:
            reasons["Lead time / stock availability"] += 2
            reasons["Delivery SLA"] += 1
        if "incumbent can ship in 5 days" in s or "incumbent" in s:
            reasons["Competitor advantage"] += 2
            reasons["Lead time / stock availability"] += 1
        if "freight" in s:
            reasons["Freight cost"] += 2
        if "price" in s or "pricing" in s:
            reasons["Price sensitivity"] += 1

    ranked = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
    lines = ["Top loss drivers (heuristic):"]
    for k, v in ranked:
        if v > 0:
            lines.append(f"• {k}: score {v}")
    return ChatResponse(
        reply="\n".join(lines),
        reasons=[k for k, v in ranked if v > 0]
    )

def build_summary(lead: Dict) -> ChatResponse:
    l = lead["lead"]
    c = lead["company"]
    d = lead["deal"]
    lines = [
        f"Lead: {l['firstName']} {l['lastName']} ({l['title']}, {l['department']})",
        f"Company: {c['name']} — {c['industry']} — Size: {c['size']}",
        f"Stage: {l['stage']} — Status: {l['status']} — Value: ${l['estValue']:,}",
        f"Products: {', '.join(d.get('products', []))}",
        f"Primary loss reason: {d['lostReasonPrimary']}",
    ]
    if d.get("lostReasonSecondary"):
        lines.append("Secondary factors: " + ", ".join(d["lostReasonSecondary"]))
    return ChatResponse(reply="\n".join(lines), reasons=[d["lostReasonPrimary"]] + d.get("lostReasonSecondary", []))

def build_coaching(lead: Dict) -> ChatResponse:
    l, c = lead["lead"], lead["company"]
    pref = next((n["text"] for n in lead.get("notes", []) if "prefers" in n.get("text","").lower()), None)
    channel_tip = f"Tip: {pref}" if pref else "Tip: Start on the buyer’s preferred channel; confirm a time before calling."

    email_example = (
        f"Subject: Quick path to a 7-day ship option for {c['name']}\n\n"
        f"Hi {l['firstName']},\n\n"
        "Thanks again for the candid feedback on timelines. We can hold an alternate mix that ships within 7 days "
        "from our nearby DC and bundle deliveries to reduce freight. If helpful, I can send a 1-page comparison "
        "with lead times and cost impact.\n\n"
        "Would a brief call tomorrow between 10–12 your time work? If not, I’ll adjust.\n\n"
        "Best,\nYour Name"
    )

    call_script = (
        "30-second call opener:\n"
        "• Thank them for time; confirm it’s still a good moment.\n"
        "• Anchor on their priority: “You mentioned 2-week ship risk. I can hold alternates with 7-day ship and "
        "bundle windows to trim freight. If that removes the schedule risk, would you want me to send the 1-pager?”\n"
        "• Close on next step: schedule review or send comparison."
    )

    objections = [
        "“Incumbent can ship in 5 days.” → Acknowledge, offer 7-day + freight bundle + post-install credit.",
        "“Price is tight.” → Frame TCO: fewer drops, lower freight; offer alternates keeping spec intact.",
        "“Risk of change.” → Start with a pilot PO or partial release; provide references if available."
    ]

    reply = [
        "Conversation coaching:",
        f"- {channel_tip}",
        "",
        "Email you can send:",
        email_example,
        "",
        call_script,
        "",
        "Likely objections & concise responses:",
        *[f"• {o}" for o in objections]
    ]
    return ChatResponse(reply="\n".join(reply), next_steps=["Send email", "Schedule review", "Prepare 1-pager"])

def build_stakeholders(lead: Dict) -> ChatResponse:
    l, c, d = lead["lead"], lead["company"], lead["deal"]
    roles_to_target = [
        ("Primary", f"{l['title']} ({l['department']}) — {l['firstName']} {l['lastName']}"),
        ("Operations", "Ops Director / Project Manager (delivery windows, site schedule)"),
        ("Finance/Procurement", "Cost approver (freight bundling, alternates sign-off)"),
        ("End User/GC", "Field lead to validate alternates meet spec")
    ]
    approach = [
        "Start with your champion (Ashley). Confirm the delivery constraint and align on ‘what good looks like’.",
        "Parallel-path Ops to validate 7-day alternates and delivery bundling feasibility.",
        "Bring Procurement/Finance in only after Ops confirms schedule fit; present TCO deltas (fewer drops, lower freight).",
        "If needed, secure a small pilot PO to de-risk switching from incumbent."
    ]
    reply = [
        f"Stakeholder approach for {c['name']}:",
        *[f"• {k}: {v}" for k, v in roles_to_target],
        "",
        "Suggested sequence:",
        *[f"1.{i+1} {step}" for i, step in enumerate(approach)],
        "",
        f"Context: primary driver is **{d['lostReasonPrimary']}**; observed signals: {', '.join(lead.get('insights', {}).get('signals', [])) or '—'}."
    ]
    return ChatResponse(reply="\n".join(reply), meta={"stakeholders": roles_to_target})

def build_priority(lead: Dict) -> ChatResponse:
    tasks = lead.get("tasks", [])
    salvage = lead.get("deal", {}).get("salvagePlay", [])

    tasks_sorted = sorted(tasks, key=lambda t: (t.get("done", False), t.get("due", "9999-12-31")))
    top_tasks = [f"{'[x]' if t.get('done') else '[ ]'} {t['title']} (due {t.get('due','TBD')})" for t in tasks_sorted]

    nba = [
        "Confirm delivery requirement (7-day vs 5-day acceptable?) with Ashley.",
        "Send 1-pager: alternates + lead times + freight bundling impact.",
        "Hold inventory for proposed alternates (tentative) and get Ops approval.",
    ]
    nba += [f"Optional: {p}" for p in salvage]

    reply = [
        "Priority plan (next best actions):",
        *[f"• {s}" for s in nba],
        "",
        "Your current tasks:",
        *[f"• {line}" for line in top_tasks[:5]]
    ]
    return ChatResponse(reply="\n".join(reply), next_steps=nba)

def build_general(lead: Dict, msg: str) -> ChatResponse:
    l, c, d = lead["lead"], lead["company"], lead["deal"]
    pref_note = next((n["text"] for n in lead.get("notes", []) if "prefers" in n.get("text","").lower()), None)
    tip = f"\nTip: {pref_note}" if pref_note else ""

    examples = [
        "Why did we lose this deal?",
        "Show me the timeline and evidence.",
        "How can we recover this deal?",
        "Draft a recovery email to Ashley.",
        "Give me a 30-second call script.",
        "How should I approach the stakeholders at GMS?",
        "Prioritize my next steps for this lead.",
        "Summarize this deal in 3 bullets.",
        "List likely objections and short responses.",
        "Create a to-do list for today."
    ]

    reply = (
        f"You’re viewing {l['firstName']} {l['lastName']} at {c['name']} "
        f"(stage: {l['stage']}, status: {l['status']}, value: ${l['estValue']:,}).\n\n"
        "I can help with:\n"
        "• Why we lost this deal\n"
        "• The evidence/timeline\n"
        "• Recovery/salvage steps\n"
        "• Conversation coaching (email/call scripts, objections)\n"
        "• Stakeholder approach plan\n"
        "• Priority plan and next-best actions\n\n"
        "Try asking:\n" + "\n".join(f"• {q}" for q in examples) + tip
    )
    return ChatResponse(reply=reply)

# ---------------------------
# Routes
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    lead = LEADS.get(req.leadId)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    print(req.message)

    intent = req.force_intent or classify_intent(req.message)

    if intent == "why_lost":
        return build_why_lost(lead)
    elif intent == "salvage":
        return build_salvage(lead)
    elif intent == "timeline":
        return build_timeline(lead)
    elif intent == "evidence":
        return build_evidence(lead)
    elif intent == "drivers":
        return build_drivers(lead)
    elif intent == "summary":
        return build_summary(lead)
    elif intent == "coaching":
        return build_coaching(lead)
    elif intent == "stakeholders":
        return build_stakeholders(lead)
    elif intent == "priority":
        return build_priority(lead)
    else:
        return build_general(lead, req.message)
