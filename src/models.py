from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes_on_outline_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_outline_notes: Mapped[str] = mapped_column(String(50), default="no", nullable=False)
    final_review_notes_status: Mapped[str] = mapped_column(
        String(50),
        default="no",
        nullable=False,
    )
    final_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    book_output_status: Mapped[str] = mapped_column(
        String(50),
        default="not_ready",
        nullable=False,
    )
    output_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    outlines: Mapped[list["Outline"]] = relationship(back_populates="book")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="book")


class Outline(Base):
    __tablename__ = "outlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, index=True)
    outline_text: Mapped[str] = mapped_column(Text, nullable=False)
    notes_on_outline_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    book: Mapped[Book] = relationship(back_populates="outlines")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_notes_status: Mapped[str] = mapped_column(String(50), default="no", nullable=False)
    chapter_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    book: Mapped[Book] = relationship(back_populates="chapters")
