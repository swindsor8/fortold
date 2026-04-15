import uuid
from datetime import datetime

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    plans: Mapped[list["Plan"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
    runs: Mapped[list["Run"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa: F821
