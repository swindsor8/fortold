import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.plan import Plan
from app.schemas.plan import PlanJson, PlanResponse
from app.services.datasets import get_dataset_version

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert ML engineer advising on experiment planning.
Respond with ONLY a valid JSON object — no prose, no markdown, no code fences.
The JSON must conform exactly to this schema:
{
  "task_type": "classification" | "regression",
  "target_column": "<column name that exists in the schema>",
  "feature_columns": ["<col1>", ...],
  "feature_selection_strategy": "<strategy description>",
  "model_choices": [
    {
      "name": "<class name>",
      "library": "sklearn" | "xgboost",
      "hyperparameters": { ... }
    }
  ],
  "validation_method": "<method string>",
  "metrics": ["<metric1>", ...],
  "preprocessing": {
    "imputation": "mean" | "median" | "most_frequent" | "constant",
    "scaling": "standard" | "minmax" | "none",
    "encode_categoricals": true | false
  },
  "risks": ["<risk1>", ...],
  "confidence_level": "low" | "medium" | "high",
  "rationale": "<1-2 sentences>"
}

Rules:
- target_column MUST be a column that exists in the provided schema
- feature_columns must NOT include target_column
- model_choices must have 1-3 entries
- Allowed sklearn class names: LogisticRegression, RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor, Ridge, Lasso, SVR, SVC
- Allowed xgboost class names: XGBClassifier, XGBRegressor
- hyperparameters must contain only JSON-serializable primitive values
- validation_method format: "stratified_kfold_5", "kfold_5", or "holdout_0.2"
- For classification, metrics must include at least one of: accuracy, f1, roc_auc, precision, recall
- For regression, metrics must include at least one of: rmse, mae, r2\
"""


def _build_user_message(dataset_version) -> str:
    schema_lines = []
    for col in dataset_version.column_schema:
        name = col["name"] if isinstance(col, dict) else col.name
        dtype = col["dtype"] if isinstance(col, dict) else col.dtype
        null_pct = col["null_pct"] if isinstance(col, dict) else col.null_pct
        n_unique = col["n_unique"] if isinstance(col, dict) else col.n_unique
        sample = col["sample_values"] if isinstance(col, dict) else col.sample_values
        schema_lines.append(
            f"- {name} ({dtype}): {null_pct:.1f}% null, {n_unique} unique values, sample: {sample}"
        )

    schema_str = "\n".join(schema_lines)
    row_count = dataset_version.row_count or "unknown"
    file_size = dataset_version.file_size_bytes or "unknown"

    return (
        f"Dataset goal: {dataset_version.goal}\n\n"
        f"Column schema:\n{schema_str}\n\n"
        f"Dataset stats:\n"
        f"- Row count: {row_count}\n"
        f"- File size: {file_size} bytes\n\n"
        "Generate an ML experiment plan for this dataset."
    )


async def generate_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
) -> Plan:
    dataset_version = await get_dataset_version(db, user_id, dataset_version_id)

    user_message = _build_user_message(dataset_version)
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            ),
            timeout=settings.llm_timeout_seconds,
        )
    except TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="LLM request timed out")

    raw_text = response.content[0].text.strip()
    prompt_tokens = response.usage.input_tokens
    completion_tokens = response.usage.output_tokens

    try:
        parsed = json.loads(raw_text)
        validated = PlanJson(**parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("LLM returned invalid plan. Raw: %s | Error: %s", raw_text, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned an invalid plan structure. Please try again.",
        )

    plan = Plan(
        user_id=user_id,
        dataset_version_id=dataset_version_id,
        status="draft",
        plan_json=validated.model_dump(),
        llm_model=settings.llm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> Plan:
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


async def list_plans_for_version(
    db: AsyncSession, user_id: uuid.UUID, dataset_version_id: uuid.UUID
) -> list[Plan]:
    result = await db.execute(
        select(Plan)
        .where(Plan.dataset_version_id == dataset_version_id, Plan.user_id == user_id)
        .order_by(Plan.created_at.desc())
    )
    return list(result.scalars().all())


async def review_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
    action: str,
) -> Plan:
    plan = await get_plan(db, user_id, plan_id)
    if plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan is already '{plan.status}' and cannot be reviewed again",
        )
    plan.status = action  # "approve" maps to approved? No — action is "approve"|"reject"
    # The DB enum uses "approved"/"rejected", action is "approve"/"reject"
    plan.status = "approved" if action == "approve" else "rejected"
    plan.reviewed_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(plan)
    return plan
