import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.plan import PlanGenerateRequest, PlanResponse, PlanReviewRequest
from app.services.auth import get_current_user
from app.services.plans import generate_plan, get_plan, list_plans_for_version, review_plan

router = APIRouter()


@router.post("/generate", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan_route(
    body: PlanGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await generate_plan(db, current_user.id, body.dataset_version_id)


@router.get("/", response_model=list[PlanResponse])
async def list_plans_route(
    dataset_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_plans_for_version(db, current_user.id, dataset_version_id)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan_route(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_plan(db, current_user.id, plan_id)


@router.post("/{plan_id}/review", response_model=PlanResponse)
async def review_plan_route(
    plan_id: uuid.UUID,
    body: PlanReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await review_plan(db, current_user.id, plan_id, body.action)
