"""
TaxFlow CRM — Deadline Routes
Tax deadline management with auto-generation and dashboard feeds.
"""
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..db import (
    create_deadline, get_deadlines_for_client, update_deadline,
    delete_deadline, get_upcoming_deadlines, get_client,
    auto_generate_deadlines
)
from ..models import DeadlineCreate, DeadlineUpdate, DeadlineOut, DeadlineType

router = APIRouter(prefix="/deadlines", tags=["Deadlines"])


def _add_days_until(deadline: dict) -> dict:
    """Add days_until computed field to deadline dict."""
    if deadline.get("due_date"):
        try:
            due = date.fromisoformat(str(deadline["due_date"]))
            deadline["days_until"] = (due - date.today()).days
        except (ValueError, TypeError):
            deadline["days_until"] = None
    return deadline


@router.get("/upcoming", response_model=list[DeadlineOut])
async def get_upcoming(
    days: int = Query(30, ge=1, le=365),
    preparer_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all upcoming deadlines across all clients within N days.
    Powers the dashboard deadline feed.
    """
    deadlines = await get_upcoming_deadlines(days=days, preparer_id=preparer_id)
    return [_add_days_until(d) for d in deadlines]


@router.get("/calendar")
async def get_deadline_calendar(
    year: int = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns standard US tax deadlines for a given year.
    Useful for reference and auto-population.
    """
    y = year or date.today().year
    return {
        "year": y,
        "federal_deadlines": [
            {"date": f"{y}-01-31", "label": "W-2 & 1099-NEC employer filing deadline"},
            {"date": f"{y}-01-15", "label": f"Q4 {y-1} Estimated Tax Payment due"},
            {"date": f"{y}-03-15", "label": "S-Corp & Partnership returns due (or extension)"},
            {"date": f"{y}-04-15", "label": "Individual 1040 & C-Corp returns due"},
            {"date": f"{y}-04-15", "label": f"Q1 {y} Estimated Tax Payment due"},
            {"date": f"{y}-06-15", "label": f"Q2 {y} Estimated Tax Payment due"},
            {"date": f"{y}-09-15", "label": f"Q3 {y} Estimated Tax Payment due"},
            {"date": f"{y}-09-15", "label": "S-Corp & Partnership extension deadline"},
            {"date": f"{y}-10-15", "label": "Individual 1040 extension deadline"},
            {"date": f"{y}-04-15", "label": "FBAR (FinCEN 114) filing deadline"},
            {"date": f"{y}-10-15", "label": "FBAR extension deadline"},
        ],
        "note": "Deadlines may shift to next business day if they fall on a weekend or federal holiday."
    }


@router.get("/client/{client_id}", response_model=list[DeadlineOut])
async def get_client_deadlines(
    client_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get all deadlines for a specific client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    deadlines = await get_deadlines_for_client(client_id)
    return [_add_days_until(d) for d in deadlines]


@router.post("/client/{client_id}/auto-generate", status_code=201)
async def auto_generate_client_deadlines(
    client_id: int,
    tax_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Auto-generate standard deadlines based on client entity type.
    Will not duplicate existing deadlines.
    """
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    year = tax_year or client["tax_year"]
    deadlines_data = auto_generate_deadlines(client_id, client["entity_type"], year)

    # Check for duplicates
    existing = await get_deadlines_for_client(client_id)
    existing_types = {d["deadline_type"] for d in existing}

    created = []
    for dl in deadlines_data:
        if dl["deadline_type"] not in existing_types:
            deadline = await create_deadline(dl)
            created.append(deadline)

    return {
        "message": f"Generated {len(created)} deadlines for {client['full_name']}",
        "created": len(created),
        "deadlines": created,
    }


@router.post("", response_model=DeadlineOut, status_code=201)
async def create_new_deadline(
    data: DeadlineCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a custom deadline for a client."""
    client = await get_client(data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    deadline = await create_deadline(data.model_dump())
    return _add_days_until(deadline)


@router.patch("/{deadline_id}", response_model=DeadlineOut)
async def update_deadline_record(
    deadline_id: int,
    data: DeadlineUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update deadline status or due date."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    deadline = await update_deadline(deadline_id, update_data)
    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")
    return _add_days_until(deadline)


@router.delete("/{deadline_id}", status_code=204)
async def delete_deadline_record(
    deadline_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not await delete_deadline(deadline_id):
        raise HTTPException(status_code=404, detail="Deadline not found")


@router.get("/types")
async def list_deadline_types(current_user: dict = Depends(get_current_user)):
    """Get all available deadline types."""
    return [{"value": dt.value, "label": dt.value} for dt in DeadlineType]
