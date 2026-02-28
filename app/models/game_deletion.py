import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameDeletionRequestStatus(str, enum.Enum):
    pending = "pending"


class GameDeletionRequest(Base):
    __tablename__ = "game_deletion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, unique=True, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[GameDeletionRequestStatus] = mapped_column(
        Enum(GameDeletionRequestStatus), nullable=False, default=GameDeletionRequestStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GameDeletionApproval(Base):
    __tablename__ = "game_deletion_approvals"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_game_deletion_approval_request_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("game_deletion_requests.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
