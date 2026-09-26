"""
TaxFlow CRM — AI Assistant Routes
Context-aware AI assistant powered by OpenAI/DeepSeek.
Knows about tax deadlines, missing documents, client profiles.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ..auth import get_current_user
from ..config import get_settings
from ..models import AssistantChatRequest, AssistantChatResponse

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])
settings = get_settings()

# ─── Tax-Aware System Prompt ──────────────────────────────────────────────────

TAXFLOW_SYSTEM_PROMPT = """You are TaxFlow AI, an expert assistant embedded in TaxFlow CRM — 
a practice management system built for US tax professionals and CPA firms.

Your role:
- Help tax preparers and accountants manage their clients efficiently
- Answer questions about US tax procedures, deadlines, and document requirements
- Draft professional client communications (emails, reminder notices, extension notifications)
- Analyze client situations and flag potential issues
- Suggest follow-up actions based on client status

Your domain vocabulary includes:
- Federal return forms such as 1040, 1120, 1120-S, 1065, and 990
- Entity types such as Individual, LLC, S-Corp, C-Corp, Partnership, and Sole Proprietor
- Common tax documents such as W-2, 1099 forms, K-1, 1098, and Schedule C/E
- Filing, extension, estimated-payment, correspondence, and state-tax workflows

Deadline safety:
- Do not treat dates embedded in this system prompt or model memory as current authority.
- For client-specific deadline questions, use only the deadline records supplied in CLIENT CONTEXT.
- For general/current deadline questions without an authoritative application record, state that the demo has no live authoritative tax-calendar source and recommend verifying the relevant IRS/state source before acting.

Communication style:
- Professional, clear, and accurate
- Draft client emails in a warm but professional tone
- Flag urgent issues clearly
- When drafting emails, always include subject line, greeting, and professional signature placeholder

IMPORTANT:
- Always distinguish general guidance from client-specific analysis.
- Never give definitive legal/tax advice; recommend verification by the responsible preparer.
- Treat CLIENT CONTEXT as operational application data, not as authorization to file, submit, pay, or contact a client.
- Suggested actions are drafts only; do not imply that an external action has been performed.
"""


def build_client_context(summary: dict, privacy_mode: str = "minimum") -> str:
    """Build minimized outbound LLM context from client summary data.

    Sensitive CRM fields such as SSN last four, EIN, phone, address, notes, and
    portal credentials are never included. Full name/email require the explicit
    "identity" privacy mode; the default uses only an internal client reference.
    """
    client = summary.get("client", {})
    stats = summary.get("document_stats", {})
    missing = summary.get("missing_documents", [])
    upcoming = summary.get("upcoming_deadlines", [])
    missed = summary.get("missed_deadlines", [])
    tasks = summary.get("open_tasks", [])

    identity_lines = [
        f"Client Reference: client:{client.get('id', 'unknown')}",
    ]
    if privacy_mode == "identity":
        identity_lines.extend([
            f"Name: {client.get('full_name', 'Unknown')}",
            f"Email: {client.get('email', 'N/A')}",
        ])

    ctx = f"""
=== CLIENT CONTEXT ===
Outbound Privacy Mode: {privacy_mode}
{chr(10).join(identity_lines)}
Entity Type: {client.get('entity_type', 'individual')}
Filing Status: {client.get('filing_status', 'N/A')}
Tax Year: {client.get('tax_year', 2024)}
State: {client.get('state', 'N/A')}
Assigned Preparer ID: {client.get('assigned_preparer_id', 'Unassigned')}

=== DOCUMENT STATUS ===
Completion: {stats.get('completion_pct', 0):.1f}%
Received: {stats.get('received', 0)} | Reviewed: {stats.get('reviewed', 0)} | Awaiting: {stats.get('awaiting', 0)}
Missing Documents: {', '.join(missing) if missing else 'None — all documents received'}

=== DEADLINES ===
Upcoming: {len(upcoming)}
{chr(10).join(f"  - {d['type']} due {d['due']}" for d in upcoming) if upcoming else '  None in the near future'}
Missed/Overdue: {len(missed)}
{chr(10).join(f"  - {d['type']} was due {d['due']}" for d in missed) if missed else '  None'}

=== OPEN TASKS ===
{chr(10).join(f"  - {t}" for t in tasks) if tasks else '  No open tasks'}
"""
    return ctx.strip()


async def get_ai_client():
    """Get configured OpenAI-compatible client."""
    try:
        from openai import AsyncOpenAI
        kwargs = {"api_key": settings.ai_api_key}
        if settings.ai_base_url:
            kwargs["base_url"] = settings.ai_base_url
        return AsyncOpenAI(**kwargs)
    except ImportError:
        raise HTTPException(status_code=500, detail="OpenAI library not installed")


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    request: AssistantChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Main AI assistant endpoint.
    If client_id is provided, context is enriched with client's full profile,
    missing documents, deadlines, and recent messages.
    """
    if not settings.ai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant not configured. Set OPENAI_API_KEY or DEEPSEEK_API_KEY in .env"
        )

    messages = [{"role": "system", "content": TAXFLOW_SYSTEM_PROMPT}]

    # Add client context if provided
    client_context = ""
    client_name = None
    privacy_mode = getattr(settings, "ai_context_privacy", "minimum")
    client_identity_sent = False
    if request.client_id:
        try:
            from ..db import get_client
            from ..routes.clients import router as clients_router
            from ..db import (
                get_documents_for_client, get_deadlines_for_client,
                get_tasks_for_client, get_messages_for_client,
                get_document_completion
            )
            from datetime import date

            client = await get_client(request.client_id)
            if client:
                client_name = client["full_name"]
                docs = await get_documents_for_client(request.client_id)
                deadlines = await get_deadlines_for_client(request.client_id)
                tasks = await get_tasks_for_client(request.client_id)
                completion = await get_document_completion(request.client_id)

                today = date.today()
                upcoming = [
                    d for d in deadlines
                    if d["status"] in ("upcoming", "in_progress")
                ]
                missed = [
                    d for d in deadlines
                    if d["status"] == "missed" or
                    (d["status"] == "upcoming" and d["due_date"] < today.isoformat())
                ]
                missing_docs = [d for d in docs if d["status"] == "awaiting"]

                summary = {
                    "client": client,
                    "document_stats": completion,
                    "missing_documents": [d["doc_type"] for d in missing_docs],
                    "upcoming_deadlines": [
                        {"type": d["deadline_type"], "due": d["due_date"], "status": d["status"]}
                        for d in upcoming[:5]
                    ],
                    "missed_deadlines": [
                        {"type": d["deadline_type"], "due": d["due_date"]}
                        for d in missed
                    ],
                    "open_tasks": [t["title"] for t in tasks if not t["completed"]],
                }
                client_context = build_client_context(summary, privacy_mode=privacy_mode)
                client_identity_sent = privacy_mode == "identity"
                messages.append({"role": "system", "content": client_context})

        except Exception as e:
            logger.warning(f"Could not load client context: {e}")

    # Add conversation history
    if request.conversation_history:
        for msg in request.conversation_history[-10:]:  # Last 10 messages
            messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": request.message})

    # Call AI
    try:
        client = await get_ai_client()
        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )
        reply = response.choices[0].message.content

        # Extract suggested actions from common patterns
        suggested = _extract_suggested_actions(request.message, reply)

        logger.info(
            f"AI assistant query by user {current_user['id']} "
            f"{'for client ' + str(request.client_id) if request.client_id else '(global)'}"
        )

        return AssistantChatResponse(
            reply=reply,
            suggested_actions=suggested,
            referenced_client=client_name,
            context_privacy_mode=privacy_mode,
            client_identity_sent=client_identity_sent,
        )

    except Exception as e:
        logger.error(f"AI assistant error: {e}")
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")


def _extract_suggested_actions(user_message: str, ai_reply: str) -> list[str]:
    """Suggest follow-up actions based on the conversation context."""
    message_lower = user_message.lower()
    suggestions = []

    if any(word in message_lower for word in ["reminder", "email", "draft", "send"]):
        suggestions.append("Copy email to clipboard")
        suggestions.append("Send via Messages")

    if any(word in message_lower for word in ["missing", "documents", "checklist"]):
        suggestions.append("View document checklist")
        suggestions.append("Send document request to client")

    if any(word in message_lower for word in ["deadline", "extension", "due"]):
        suggestions.append("View deadline timeline")
        suggestions.append("Mark extension filed")

    if any(word in message_lower for word in ["at-risk", "behind", "overdue"]):
        suggestions.append("View all at-risk clients")
        suggestions.append("Generate bulk reminders")

    return suggestions[:3]  # Max 3 suggestions


@router.get("/prompts")
async def get_suggested_prompts(
    client_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Return context-aware suggested prompts for the AI assistant.
    """
    global_prompts = [
        "Who are my at-risk clients this week?",
        "Show me all clients with deadlines in the next 7 days",
        "Which clients haven't submitted their W-2s yet?",
        "Draft a general tax season reminder email",
        "What are the Q3 2025 estimated tax payment dates?",
        "What documents does an S-Corp need for their 2024 return?",
        "Summarize what I need to do today",
        "What's the deadline for filing a 1099-NEC?",
        "Draft an extension filing notice for clients",
    ]

    if not client_id:
        return {"prompts": global_prompts}

    client_prompts = [
        f"What documents is this client still missing?",
        f"Draft a reminder email asking for missing documents",
        f"What are this client's upcoming deadlines?",
        f"Is this client at risk of missing their filing deadline?",
        f"Draft an extension notice for this client",
        f"Summarize this client's tax situation",
        f"What should I follow up on with this client?",
        f"Draft a message asking about their business expenses",
    ]

    return {"prompts": client_prompts, "client_id": client_id}
