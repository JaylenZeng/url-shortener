import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
  pass

class User(Base):
  __tablename__ = "users"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
  password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )
  
  links: Mapped[list["Link"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Link(Base):
  __tablename__ = "links"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  short_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
  original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
  user_id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )
  expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, index=True
  )
  
  user: Mapped["User"] = relationship(back_populates="links")
  
class ClickEvent(Base):
  __tablename__ = "click_events"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  link_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("links.id"), nullable=False
  )
  timestamp: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
  )
  user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
  referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
  ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
  
  __table_args__ = (
    Index("ix_click_events_link_id_timestamp", "link_id", "timestamp"),
  )