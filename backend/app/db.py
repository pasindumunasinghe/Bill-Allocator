from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


def new_id():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    files: Mapped[list["BillFile"]] = relationship(back_populates="batch", cascade="all, delete-orphan",
                                                   order_by="BillFile.created_at")


class BillFile(Base):
    __tablename__ = "bill_files"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    batch: Mapped[Batch] = relationship(back_populates="files")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    file_name: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))
    stored_path: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(64), index=True)
    group: Mapped[str | None] = mapped_column(String(1))
    contract_number: Mapped[str | None] = mapped_column(String(64))
    contract_source: Mapped[str | None] = mapped_column(String(32))  # document | filename
    subscription_number: Mapped[str | None] = mapped_column(String(64))
    bill_period: Mapped[str | None] = mapped_column(String(128))
    bill_month: Mapped[str | None] = mapped_column(String(32))
    total_charges: Mapped[object | None] = mapped_column(Numeric(20, 6))
    vat: Mapped[object | None] = mapped_column(Numeric(20, 6))
    total_without_vat: Mapped[object | None] = mapped_column(Numeric(20, 6))
    allocation_per_company: Mapped[object | None] = mapped_column(Numeric(24, 8))
    rounding_adjustment: Mapped[object | None] = mapped_column(Numeric(20, 6))
    related_company: Mapped[str | None] = mapped_column(String(128))
    cost_center: Mapped[str | None] = mapped_column(String(64))
    allocations: Mapped[list | None] = mapped_column(JSON)
    errors: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[list | None] = mapped_column(JSON)
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    read_attempts: Mapped[int] = mapped_column(Integer, default=0)
    text_excerpt: Mapped[str | None] = mapped_column(Text)


def init_db():
    Base.metadata.create_all(engine)
