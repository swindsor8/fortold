from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RunCreateRequest(BaseModel):
    plan_id: UUID


class ExperimentResultResponse(BaseModel):
    id: UUID
    run_id: UUID
    model_name: str
    split: str
    metrics: dict
    feature_importances: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: UUID
    user_id: UUID
    plan_id: UUID
    status: str
    rq_job_id: str | None
    metrics: dict | None
    model_artifacts_path: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    experiment_results: list[ExperimentResultResponse] = []

    model_config = {"from_attributes": True}
