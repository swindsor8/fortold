import io
import uuid
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.services.projects import get_project


def _build_column_schema(df: pd.DataFrame) -> list[dict]:
    schema = []
    for col in df.columns:
        series = df[col]
        sample_raw = series.dropna().head(5).tolist()
        sample = []
        for v in sample_raw:
            if hasattr(v, "item"):
                sample.append(v.item())
            else:
                sample.append(v)
        schema.append(
            {
                "name": col,
                "dtype": str(series.dtype),
                "null_pct": round(float(series.isnull().mean() * 100), 2),
                "n_unique": int(series.nunique()),
                "sample_values": sample,
            }
        )
    return schema


async def upload_csv(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    name: str,
    goal: str,
    file_bytes: bytes,
    filename: str,
) -> tuple[Dataset, DatasetVersion]:
    # Verify project ownership
    try:
        await get_project(db, user_id, project_id)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project not found or access denied")

    # Size check
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_bytes} bytes",
        )

    # Parse CSV
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot parse CSV: {exc}")

    column_schema = _build_column_schema(df)
    row_count = len(df)

    # Find or create Dataset
    result = await db.execute(
        select(Dataset).where(
            Dataset.name == name,
            Dataset.project_id == project_id,
            Dataset.user_id == user_id,
        )
    )
    dataset = result.scalar_one_or_none()

    if dataset is None:
        dataset = Dataset(user_id=user_id, project_id=project_id, name=name)
        db.add(dataset)
        await db.flush()  # get dataset.id before using it
        version_number = 1
    else:
        max_result = await db.execute(
            select(func.max(DatasetVersion.version_number)).where(
                DatasetVersion.dataset_id == dataset.id
            )
        )
        current_max = max_result.scalar() or 0
        version_number = current_max + 1

    # Write file
    file_path = Path(settings.upload_dir) / str(user_id) / str(dataset.id) / f"v{version_number}.csv"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_bytes)

    # Create DatasetVersion
    version = DatasetVersion(
        dataset_id=dataset.id,
        user_id=user_id,
        version_number=version_number,
        file_path=str(file_path),
        file_size_bytes=len(file_bytes),
        row_count=row_count,
        column_schema=column_schema,
        goal=goal,
    )
    db.add(version)
    await db.commit()
    await db.refresh(dataset)
    await db.refresh(version)
    return dataset, version


async def list_dataset_versions(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[DatasetVersion]:
    result = await db.execute(
        select(DatasetVersion)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
        .where(Dataset.project_id == project_id, DatasetVersion.user_id == user_id)
        .order_by(DatasetVersion.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_dataset_version(
    db: AsyncSession,
    user_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DatasetVersion:
    result = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id,
            DatasetVersion.user_id == user_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
    return version
