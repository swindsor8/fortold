import uuid

import redis as redis_lib
import rq
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.plan import Plan
from app.models.run import Run


async def create_run(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> Run:
    # Fetch plan with ownership check
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # Critical gate: only approved plans can be run
    if plan.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Plan must be approved before starting a run",
        )

    run = Run(user_id=user_id, plan_id=plan_id, status="queued")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Enqueue background job using synchronous Redis client (RQ requirement)
    redis_conn = redis_lib.Redis.from_url(settings.redis_url)
    queue = rq.Queue(settings.rq_queue_name, connection=redis_conn)
    job = queue.enqueue(
        "app.worker.ml.trainer.train_model",
        run_id=str(run.id),
        job_timeout=3600,
    )

    run.rq_job_id = job.id
    await db.commit()
    await db.refresh(run)
    return run


async def get_run(
    db: AsyncSession,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> Run:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.experiment_results))
        .where(Run.id == run_id, Run.user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


async def list_runs_for_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> list[Run]:
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.experiment_results))
        .where(Run.plan_id == plan_id, Run.user_id == user_id)
        .order_by(Run.created_at.desc())
    )
    return list(result.scalars().all())
