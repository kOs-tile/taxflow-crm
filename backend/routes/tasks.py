"""
TaxFlow CRM — Task Routes
Per-client task and note management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..db import create_task, get_tasks_for_client, update_task, get_client
from ..models import TaskCreate, TaskUpdate, TaskOut

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/client/{client_id}", response_model=list[TaskOut])
async def get_client_tasks(
    client_id: int,
    include_completed: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    """Get all tasks for a client."""
    client = await get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    tasks = await get_tasks_for_client(client_id)
    if not include_completed:
        tasks = [t for t in tasks if not t["completed"]]
    return tasks


@router.post("", response_model=TaskOut, status_code=201)
async def create_client_task(
    data: TaskCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new task for a client."""
    client = await get_client(data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return await create_task(data.model_dump())


@router.patch("/{task_id}", response_model=TaskOut)
async def update_client_task(
    task_id: int,
    data: TaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update task details or mark complete."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    task = await update_task(task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Mark a task as complete."""
    task = await update_task(task_id, {"completed": True})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task completed", "task": task}


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a task."""
    from ..db import get_db
    async with await get_db() as db:
        cur = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
