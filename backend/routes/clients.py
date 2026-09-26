"""
TaxFlow CRM — Client Routes
Full CRUD + search/filter + document completion enrichment.
"""
import sqlite3
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..auth import get_current_user, hash_password
from ..db import (
    create_client, get_client, list_clients, update_client, delete_client,
    get_document_completion, get_unread_message_counts,
    get_deadlines_for_client, auto_generate_deadlines, create_deadline,
    list_users, create_user, get_user_by_email
)
from ..models import (
    ClientCreate, ClientUpdate, ClientOut, ClientSummary, UserCreate, UserOut
)

router = APIRouter(prefix="/clients", tags=["Clients"])


def _enrich_client(client: dict, completion: Optional[dict] = None, unread: int = 0) -> dict:
    """Add computed fields to client dict."""
    client["document_completion_pct"] = completion["completion_pct"] if completion else None
    client["unread_message_count"] = unread
    return client


@router.get("", response_model=list[ClientOut])
async def list_all_clients(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    preparer_id: Optional[int] = Query(None),
    entity_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    tax_year: Optional[int] = Query(None),
    enrich: bool = Query(True, description="Include document_completion_pct"),
    current_user: dict = Depends(get_current_user),
):
    """List all clients with optional filters."""
    clients = await list_clients(
        preparer_id=preparer_id,
        entity_type=entity_type,
        is_active=is_active,
        search=search,
        tax_year=tax_year,
    )

    if enrich:
        unread_map = await get_unread_message_counts()
        result = []
        for c in clients:
            completion = await get_document_completion(c["id"])
            c = _enrich_client(c, completion, unread_map.get(c["id"], 0))
            result.append(c)
        return result

    return clients


@router.post("", response_model=ClientOut, status_code=201)
async def create_new_client(
    data: ClientCreate,
    auto_deadlines: bool = Query(True, description="Auto-generate standard deadlines"),
    current_user: dict = Depends(get_current_user),
):
    """Create a new client. Optionally auto-generates tax deadlines."""
    portal_password = data.portal_password
    client_dict = data.model_dump(exclude={"portal_password"})

    if portal_password:
        client_dict["portal_password_hash"] = hash_password(portal_password)

    try:
        client = await create_client(client_dict)
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(status_code=409, detail="A client with this email already exists.")
        raise HTTPException(status_code=400, detail=str(e))

    # Auto-generate standard deadlines
    if auto_deadlines:
        deadlines = auto_generate_deadlines(
            client["id"], data.entity_type.value, data.tax_year
        )
        for dl in deadlines:
            await create_deadline(dl)

    return client


@router.get("/{client_id}", response_model=ClientOut)
async def get_client_detail(
    client_id: int,
    current_user: dict = Depends(get_current_user),
):
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    completion = await get_document_completion(client_id)
    unread_map = await get_unread_message_counts()
    return _enrich_client(client, completion, unread_map.get(client_id, 0))


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client_record(
    client_id: int,
    data: ClientUpdate,
    current_user: dict = Depends(get_current_user),
):
    existing = await get_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    client = await update_client(client_id, update_data)
    return client


@router.delete("/{client_id}", status_code=204)
async def delete_client_record(
    client_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not await delete_client(client_id):
        raise HTTPException(status_code=404, detail="Client not found")


@router.post("/{client_id}/portal-password")
async def set_client_portal_password(
    client_id: int,
    password: str = Body(..., embed=True, min_length=8),
    current_user: dict = Depends(get_current_user),
):
    """Set or update the client's portal login password."""
    existing = await get_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Client not found")

    await update_client(client_id, {"portal_password_hash": hash_password(password)})
    return {"message": "Portal password updated successfully"}


@router.get("/{client_id}/summary")
async def get_client_summary(
    client_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get a comprehensive summary for the AI assistant context."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from ..db import (
        get_documents_for_client, get_deadlines_for_client, get_tasks_for_client,
        get_messages_for_client
    )
    from datetime import date

    docs = await get_documents_for_client(client_id)
    deadlines = await get_deadlines_for_client(client_id)
    tasks = await get_tasks_for_client(client_id)
    messages = await get_messages_for_client(client_id, limit=5)
    completion = await get_document_completion(client_id)

    today = date.today()
    upcoming_deadlines = [
        d for d in deadlines
        if d["status"] in ("upcoming", "in_progress")
    ]
    missed_deadlines = [
        d for d in deadlines
        if d["status"] == "missed" or
        (d["status"] == "upcoming" and d["due_date"] < today.isoformat())
    ]
    missing_docs = [d for d in docs if d["status"] == "awaiting"]

    return {
        "client": client,
        "document_stats": completion,
        "missing_documents": [d["doc_type"] for d in missing_docs],
        "upcoming_deadlines": [
            {"type": d["deadline_type"], "due": d["due_date"], "status": d["status"]}
            for d in upcoming_deadlines[:5]
        ],
        "missed_deadlines": [
            {"type": d["deadline_type"], "due": d["due_date"]}
            for d in missed_deadlines
        ],
        "open_tasks": [t["title"] for t in tasks if not t["completed"]],
        "recent_messages": [
            {"role": m["sender_role"], "content": m["content"][:100]}
            for m in messages[-3:]
        ],
    }


# ─── Staff/User Management ────────────────────────────────────────────────────

users_router = APIRouter(prefix="/users", tags=["Staff Users"])


@users_router.get("", response_model=list[UserOut])
async def list_staff_users(current_user: dict = Depends(get_current_user)):
    users = await list_users()
    return [
        UserOut(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            role=u["role"],
            created_at=u["created_at"],
            is_active=bool(u["is_active"]),
        )
        for u in users
    ]


@users_router.post("", response_model=UserOut, status_code=201)
async def create_staff_user(
    data: UserCreate,
    current_user: dict = Depends(get_current_user),
):
    existing = await get_user_by_email(data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await create_user(
        data.email, data.full_name, data.role.value, hash_password(data.password)
    )
    return UserOut(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"],
        is_active=bool(user["is_active"]),
    )
