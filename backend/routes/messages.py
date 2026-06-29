"""
TaxFlow CRM — Messaging Routes
Secure in-app messaging between staff and clients.
SSE endpoint for real-time new message notifications.
"""
import asyncio
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from ..auth import get_current_user, get_current_client_or_staff
from ..db import (
    create_message, get_messages_for_client, mark_messages_read,
    get_all_message_threads, get_client
)
from ..models import MessageCreate, MessageOut, MessageThread

router = APIRouter(prefix="/messages", tags=["Messages"])

# In-memory SSE subscriber queues: {client_id: [queue, ...]}
_sse_subscribers: dict[int, list[asyncio.Queue]] = {}


def _notify_sse(client_id: int, message: dict):
    """Push a new message event to all SSE subscribers watching this client."""
    if client_id in _sse_subscribers:
        for queue in _sse_subscribers[client_id]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass


@router.get("/threads")
async def get_all_threads(current_user: dict = Depends(get_current_user)):
    """
    Get all client message threads (inbox view).
    Returns one entry per client with last message preview and unread count.
    """
    return await get_all_message_threads()


@router.get("/client/{client_id}", response_model=list[MessageOut])
async def get_client_messages(
    client_id: int,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """Get full message thread for a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    messages = await get_messages_for_client(client_id, limit)

    # Mark client messages as read when staff views them
    await mark_messages_read(client_id, "client")

    return messages


@router.post("/client/{client_id}/send", response_model=MessageOut, status_code=201)
async def send_staff_message(
    client_id: int,
    data: MessageCreate,
    current_user: dict = Depends(get_current_user),
):
    """Staff sends a message to a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    msg = await create_message(
        client_id=client_id,
        sender_role="staff",
        content=data.content,
        sender_name=current_user.get("full_name", "Staff"),
    )
    logger.info(f"Staff message sent to client {client_id}")
    _notify_sse(client_id, msg)
    return msg


@router.post("/client/{client_id}/read")
async def mark_thread_read(
    client_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Mark all client messages in a thread as read (called by staff)."""
    count = await mark_messages_read(client_id, "client")
    return {"marked_read": count}


@router.get("/client/{client_id}/stream")
async def message_stream(
    client_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    SSE stream for real-time message notifications.
    Staff can listen for new messages from a specific client.
    """
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    if client_id not in _sse_subscribers:
        _sse_subscribers[client_id] = []
    _sse_subscribers[client_id].append(queue)

    async def event_generator() -> AsyncGenerator:
        try:
            yield {"event": "connected", "data": f"Listening for messages from client {client_id}"}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "new_message", "data": str(msg)}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "ping"}
        finally:
            if client_id in _sse_subscribers:
                try:
                    _sse_subscribers[client_id].remove(queue)
                except ValueError:
                    pass

    return EventSourceResponse(event_generator())


# ─── Client Portal Message Endpoints ──────────────────────────────────────────

portal_router = APIRouter(prefix="/portal/messages", tags=["Client Portal"])


@portal_router.get("", response_model=list[MessageOut])
async def portal_get_messages(
    current_auth: dict = Depends(get_current_client_or_staff),
):
    """Client portal: get own message thread."""
    if current_auth["type"] != "client":
        raise HTTPException(status_code=403, detail="Client portal access only")

    client_id = current_auth["id"]
    messages = await get_messages_for_client(client_id)

    # Mark staff messages as read when client views
    await mark_messages_read(client_id, "staff")
    return messages


@portal_router.post("/send", response_model=MessageOut, status_code=201)
async def portal_send_message(
    data: MessageCreate,
    current_auth: dict = Depends(get_current_client_or_staff),
):
    """Client portal: send a message to the accountant."""
    if current_auth["type"] != "client":
        raise HTTPException(status_code=403, detail="Client portal access only")

    client_id = current_auth["id"]
    msg = await create_message(
        client_id=client_id,
        sender_role="client",
        content=data.content,
        sender_name=current_auth.get("full_name", "Client"),
    )
    logger.info(f"Client {client_id} sent message to staff")
    _notify_sse(client_id, msg)
    return msg
