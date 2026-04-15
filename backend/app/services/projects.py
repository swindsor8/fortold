import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, DatasetVersion
from app.models.plan import Plan
from app.models.project import Project
from app.models.run import Run
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectUpdate


async def create_project(db: AsyncSession, user_id: uuid.UUID, data: ProjectCreate) -> Project:
    project = Project(user_id=user_id, name=data.name, description=data.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, user_id: uuid.UUID) -> list[ProjectListItem]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    items = []
    for project in projects:
        dataset_count_result = await db.execute(
            select(func.count()).where(Dataset.project_id == project.id, Dataset.user_id == user_id)
        )
        dataset_count = dataset_count_result.scalar() or 0

        run_count_result = await db.execute(
            select(func.count())
            .select_from(Run)
            .join(Plan, Run.plan_id == Plan.id)
            .join(DatasetVersion, Plan.dataset_version_id == DatasetVersion.id)
            .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
            .where(Dataset.project_id == project.id, Run.user_id == user_id)
        )
        run_count = run_count_result.scalar() or 0

        items.append(
            ProjectListItem(
                id=project.id,
                name=project.name,
                description=project.description,
                created_at=project.created_at,
                dataset_count=dataset_count,
                run_count=run_count,
            )
        )
    return items


async def get_project(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def update_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    project = await get_project(db, user_id, project_id)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    project.updated_at = func.now()
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    project = await get_project(db, user_id, project_id)
    await db.delete(project)
    await db.commit()
