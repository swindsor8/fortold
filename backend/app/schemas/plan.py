from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PlanGenerateRequest(BaseModel):
    dataset_version_id: UUID


class PlanReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: str | None = None


class ModelChoice(BaseModel):
    name: str
    library: str
    hyperparameters: dict


class PlanJson(BaseModel):
    """Used to validate LLM output before storing — not an ORM schema."""
    task_type: Literal["classification", "regression"]
    target_column: str
    feature_columns: list[str]
    feature_selection_strategy: str
    model_choices: list[ModelChoice]
    validation_method: str
    metrics: list[str]
    preprocessing: dict
    risks: list[str]
    confidence_level: Literal["low", "medium", "high"]
    rationale: str


class PlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    dataset_version_id: UUID
    status: str
    plan_json: dict
    llm_model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}
