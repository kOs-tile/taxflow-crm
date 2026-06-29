"""
TaxFlow CRM — Dashboard Routes
Aggregated stats, activity feed, and at-risk client overview.
"""
from fastapi import APIRouter, Depends, Query
from datetime import datetime

from ..auth import get_current_user
from ..db import (
    get_dashboard_stats, get_upcoming_deadlines,
    get_recent_activity, get_at_risk_clients,
    get_document_completion
)
from ..models import DashboardResponse, DashboardStats, ActivityItem, DeadlineOut, ClientSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    preparer_id: int = Query(None, description="Filter by preparer (admin sees all)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Main dashboard endpoint — returns:
    - Aggregate stats (total clients, docs this week, deadlines, at-risk)
    - Upcoming deadlines feed (next 14 days)
    - Recent activity stream
    - At-risk clients list
    """
    # Non-admin preparers see only their own clients
    effective_preparer_id = preparer_id
    if current_user.get("role") not in ("admin",) and not preparer_id:
        effective_preparer_id = current_user.get("id")

    stats_raw = await get_dashboard_stats()
    upcoming_raw = await get_upcoming_deadlines(days=14, preparer_id=effective_preparer_id)
    activity_raw = await get_recent_activity(limit=15)
    at_risk_raw = await get_at_risk_clients()

    # Build typed responses
    stats = DashboardStats(**stats_raw)

    upcoming_deadlines = []
    from datetime import date
    for d in upcoming_raw:
        try:
            due = date.fromisoformat(str(d["due_date"]))
            d["days_until"] = (due - date.today()).days
        except (ValueError, TypeError):
            d["days_until"] = None
        upcoming_deadlines.append(DeadlineOut(**d))

    activity = []
    for item in activity_raw:
        try:
            ts = item["timestamp"]
            if isinstance(ts, str):
                # Handle various SQLite datetime formats
                ts = ts.replace(" ", "T")
                if "." not in ts:
                    ts += ".000000"
                item["timestamp"] = datetime.fromisoformat(ts)
            activity.append(ActivityItem(**item))
        except Exception:
            pass

    at_risk = []
    for c in at_risk_raw:
        completion = await get_document_completion(c["id"])
        c["document_completion_pct"] = completion["completion_pct"]
        at_risk.append(ClientSummary(
            id=c["id"],
            full_name=c["full_name"],
            email=c["email"],
            entity_type=c["entity_type"],
            tax_year=c["tax_year"],
            assigned_preparer_id=c.get("assigned_preparer_id"),
            document_completion_pct=c["document_completion_pct"],
            is_active=bool(c["is_active"]),
        ))

    return DashboardResponse(
        stats=stats,
        upcoming_deadlines=upcoming_deadlines,
        recent_activity=activity,
        at_risk_clients=at_risk,
    )


@router.get("/stats")
async def get_stats_only(current_user: dict = Depends(get_current_user)):
    """Quick stats endpoint for polling/refresh."""
    return await get_dashboard_stats()


@router.get("/activity")
async def get_activity_feed(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Recent activity feed."""
    return await get_recent_activity(limit=limit)
