from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_pct: float
    n_unique: int
    sample_values: list


class DatasetUploadResponse(BaseModel):
    dataset_id: UUID
    dataset_version_id: UUID
    name: str
    row_count: int
    column_schema: list[ColumnInfo]
    file_size_bytes: int

    model_config = {"from_attributes": True}


class DatasetVersionResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    version_number: int
    row_count: int | None
    column_schema: list[ColumnInfo]
    goal: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}
