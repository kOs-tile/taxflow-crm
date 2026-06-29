"""
TaxFlow CRM — Document Routes
Per-client document checklist: status tracking, bulk operations, completion %.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..db import (
    create_document, get_documents_for_client, update_document,
    get_document_completion, get_client
)
from ..models import (
    DocumentCreate, DocumentUpdate, DocumentOut,
    DocumentCompletionStats, DocumentType, DocumentStatus, EntityType
)

router = APIRouter(prefix="/documents", tags=["Documents"])


# Standard document checklists by entity type
STANDARD_DOCS = {
    EntityType.individual: [
        DocumentType.w2,
        DocumentType.form_1099_nec,
        DocumentType.form_1099_int,
        DocumentType.form_1099_div,
        DocumentType.form_1099_b,
        DocumentType.form_1099_r,
        DocumentType.form_1098,
        DocumentType.charitable_donations,
        DocumentType.prior_return,
    ],
    EntityType.llc: [
        DocumentType.form_1099_nec,
        DocumentType.schedule_c,
        DocumentType.business_expenses,
        DocumentType.prior_return,
        DocumentType.vehicle_log,
    ],
    EntityType.s_corp: [
        DocumentType.form_1099_nec,
        DocumentType.business_expenses,
        DocumentType.prior_return,
        DocumentType.vehicle_log,
        DocumentType.k1,
    ],
    EntityType.c_corp: [
        DocumentType.form_1099_nec,
        DocumentType.business_expenses,
        DocumentType.prior_return,
    ],
    EntityType.partnership: [
        DocumentType.k1,
        DocumentType.business_expenses,
        DocumentType.prior_return,
        DocumentType.form_1099_nec,
    ],
    EntityType.sole_proprietor: [
        DocumentType.form_1099_nec,
        DocumentType.schedule_c,
        DocumentType.business_expenses,
        DocumentType.prior_return,
        DocumentType.vehicle_log,
    ],
    EntityType.nonprofit: [
        DocumentType.prior_return,
        DocumentType.business_expenses,
        DocumentType.charitable_donations,
    ],
}


@router.get("/client/{client_id}", response_model=list[DocumentOut])
async def get_client_documents(
    client_id: int,
    tax_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get all documents for a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_documents_for_client(client_id, tax_year)


@router.get("/client/{client_id}/stats", response_model=DocumentCompletionStats)
async def get_document_stats(
    client_id: int,
    tax_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get document completion statistics for a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_document_completion(client_id, tax_year)


@router.post("/client/{client_id}/initialize", status_code=201)
async def initialize_document_checklist(
    client_id: int,
    tax_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Initialize the standard document checklist for a client based on their entity type.
    Skips documents that already exist.
    """
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    year = tax_year or client["tax_year"]
    entity_type = EntityType(client["entity_type"])
    standard_docs = STANDARD_DOCS.get(entity_type, STANDARD_DOCS[EntityType.individual])

    existing = await get_documents_for_client(client_id, year)
    existing_types = {d["doc_type"] for d in existing}

    created = []
    for doc_type in standard_docs:
        if doc_type.value not in existing_types:
            doc = await create_document({
                "client_id": client_id,
                "doc_type": doc_type.value,
                "tax_year": year,
                "status": "awaiting",
            })
            created.append(doc)

    return {
        "message": f"Initialized {len(created)} documents",
        "created": len(created),
        "skipped": len(existing_types),
        "documents": created,
    }


@router.post("", response_model=DocumentOut, status_code=201)
async def add_document(
    data: DocumentCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a single document to a client's checklist."""
    client = await get_client(data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return await create_document(data.model_dump())


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document_status(
    doc_id: int,
    data: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update document status (awaiting → received → reviewed)."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    doc = await update_document(doc_id, update_data)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/client/{client_id}/bulk-update")
async def bulk_update_documents(
    client_id: int,
    updates: list[dict],
    current_user: dict = Depends(get_current_user),
):
    """
    Bulk update document statuses.
    updates: [{"doc_id": 1, "status": "received"}, ...]
    """
    results = []
    for upd in updates:
        doc_id = upd.get("doc_id")
        if not doc_id:
            continue
        doc = await update_document(doc_id, {
            "status": upd.get("status"),
            "notes": upd.get("notes"),
        })
        if doc:
            results.append(doc)

    return {"updated": len(results), "documents": results}


@router.get("/types", response_model=list[dict])
async def list_document_types(current_user: dict = Depends(get_current_user)):
    """Get all available document types with descriptions."""
    return [
        {"value": dt.value, "label": dt.value}
        for dt in DocumentType
    ]


@router.get("/client/{client_id}/missing")
async def get_missing_documents(
    client_id: int,
    tax_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get list of documents still awaiting from a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    docs = await get_documents_for_client(client_id, tax_year)
    missing = [d for d in docs if d["status"] == "awaiting"]
    return {
        "client_id": client_id,
        "client_name": client["full_name"],
        "missing_count": len(missing),
        "missing_documents": [d["doc_type"] for d in missing],
    }
