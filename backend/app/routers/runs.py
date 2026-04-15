import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.run import RunCreateRequest, RunResponse
from app.services.auth import get_current_user
from app.services.runs import create_run, get_run, list_runs_for_plan

router = APIRouter()


@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run_route(
    body: RunCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_run(db, current_user.id, body.plan_id)


@router.get("/", response_model=list[RunResponse])
async def list_runs_route(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_runs_for_plan(db, current_user.id, plan_id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run_route(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_run(db, current_user.id, run_id)
