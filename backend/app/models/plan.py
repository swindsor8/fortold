import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", index=True)  # draft | approved | rejected
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(back_populates="plans")  # noqa: F821
    dataset_version: Mapped["DatasetVersion"] = relationship(back_populates="plans")  # noqa: F821
    runs: Mapped[list["Run"]] = relationship(back_populates="plan", cascade="all, delete-orphan")  # noqa: F821
