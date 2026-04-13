from sqlalchemy import select

from src.db import get_session
from src.generate_chapter import (
    MODEL_NAME,
    format_previous_summaries,
    get_gemini_client,
    get_latest_chapter_versions,
    normalize_status,
    parse_chapter_response,
    summarize_chapter,
)
from src.models import Book, Chapter, Outline
from src.notifications import send_email_notification


def build_regenerate_chapter_prompt(
    book: Book,
    outline: Outline,
    chapter: Chapter,
    previous_chapters: list[Chapter],
) -> str:
    previous_context = format_previous_summaries(previous_chapters)

    return f"""
You are revising one chapter for a non-fiction book.

Book title:
{book.title}

Approved outline:
{outline.outline_text}

Previous chapter summaries:
{previous_context}

Current chapter title:
{chapter.title}

Current chapter content:
{chapter.content}

Editor notes for this chapter:
{chapter.chapter_notes}

Task:
Rewrite chapter {chapter.chapter_number} using the editor notes.

Requirements:
- Keep continuity with previous chapter summaries.
- Follow the approved outline.
- Improve the chapter based on the editor notes.
- Do not change unrelated parts unnecessarily.
- Return the response in exactly this format:

CHAPTER_TITLE: <chapter title>
CHAPTER_CONTENT:
<revised chapter content>
""".strip()


def regenerate_latest_chapter_for_latest_book() -> None:
    session = get_session()

    try:
        book = session.scalar(select(Book).order_by(Book.id.desc()))

        if book is None:
            raise RuntimeError("No book found. Import a book from Excel first.")

        if normalize_status(book.status_outline_notes) != "no_notes_needed":
            message = (
                f"Book ID {book.id} is paused: outline is not approved yet. "
                "Set status_outline_notes to 'no_notes_needed' first."
            )
            print(message)
            send_email_notification(
                subject="Chapter regeneration paused: outline not approved",
                body=message,
            )
            return

        latest_outline = session.scalar(
            select(Outline)
            .where(Outline.book_id == book.id)
            .order_by(Outline.version.desc())
        )

        if latest_outline is None:
            message = (
                f"Book ID {book.id} has no outline yet. "
                "Run src.generate_outline first."
            )
            print(message)
            send_email_notification(
                subject="Chapter regeneration paused: outline missing",
                body=message,
            )
            return

        chapter = session.scalar(
            select(Chapter)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.chapter_number.desc(), Chapter.version.desc())
        )

        if chapter is None:
            message = (
                f"Book ID {book.id} has no chapters yet. "
                "Run src.generate_chapter first."
            )
            print(message)
            send_email_notification(
                subject="Chapter regeneration paused: chapter missing",
                body=message,
            )
            return

        if normalize_status(chapter.chapter_notes_status) != "yes":
            message = (
                f"Chapter ID {chapter.id} is paused: chapter_notes_status must be "
                "'yes' before regeneration."
            )
            print(message)
            send_email_notification(
                subject="Chapter regeneration paused: status not ready",
                body=message,
            )
            return

        if not chapter.chapter_notes:
            message = (
                f"Chapter ID {chapter.id} is waiting for editor notes. "
                "Add chapter_notes before regeneration."
            )
            print(message)
            send_email_notification(
                subject="Waiting for chapter notes",
                body=message,
            )
            return

        all_previous_versions = list(
            session.scalars(
                select(Chapter)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.chapter_number < chapter.chapter_number,
                )
                .order_by(Chapter.chapter_number.asc(), Chapter.version.desc())
            )
        )
        previous_chapters = get_latest_chapter_versions(all_previous_versions)

        client = get_gemini_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_regenerate_chapter_prompt(
                book=book,
                outline=latest_outline,
                chapter=chapter,
                previous_chapters=previous_chapters,
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty revised chapter.")

        title, content = parse_chapter_response(
            response.text.strip(),
            chapter.chapter_number,
        )
        summary = summarize_chapter(client, content)

        revised_chapter = Chapter(
            book_id=book.id,
            chapter_number=chapter.chapter_number,
            title=title[:255],
            content=content,
            summary=summary,
            chapter_notes_status="no",
            chapter_notes=chapter.chapter_notes,
            version=chapter.version + 1,
        )

        session.add(revised_chapter)
        session.commit()
        session.refresh(revised_chapter)

        message = (
            f"Regenerated chapter ID {revised_chapter.id} "
            f"(chapter {revised_chapter.chapter_number}, "
            f"version {revised_chapter.version}) for book ID {book.id}."
        )
        print(message)
        send_email_notification(
            subject="Chapter regenerated and ready for review",
            body=message,
        )

    except Exception as error:
        session.rollback()
        send_email_notification(
            subject="Chapter regeneration failed",
            body=f"Chapter regeneration failed: {error}",
        )
        raise

    finally:
        session.close()


if __name__ == "__main__":
    regenerate_latest_chapter_for_latest_book()
