import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.dataset import DatasetUploadResponse, DatasetVersionResponse
from app.services.auth import get_current_user
from app.services.datasets import get_dataset_version, list_dataset_versions, upload_csv

router = APIRouter()


@router.post("/upload", response_model=DatasetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: uuid.UUID = Form(...),
    name: str = Form(...),
    goal: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes = await file.read()
    dataset, version = await upload_csv(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        name=name,
        goal=goal,
        file_bytes=file_bytes,
        filename=file.filename or name,
    )
    return DatasetUploadResponse(
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        name=dataset.name,
        row_count=version.row_count or 0,
        column_schema=version.column_schema,
        file_size_bytes=version.file_size_bytes or 0,
    )


@router.get("/", response_model=list[DatasetVersionResponse])
async def list_versions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_dataset_versions(db, current_user.id, project_id)


@router.get("/{version_id}", response_model=DatasetVersionResponse)
async def get_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_dataset_version(db, current_user.id, version_id)
