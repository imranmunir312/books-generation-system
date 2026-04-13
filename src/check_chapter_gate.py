from sqlalchemy import select

from src.db import get_session
from src.models import Book, Chapter
from src.notifications import send_email_notification


def normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def check_chapter_gate_for_latest_book() -> None:
    session = get_session()

    try:
        book = session.scalar(select(Book).order_by(Book.id.desc()))

        if book is None:
            raise RuntimeError("No book found. Import a book from Excel first.")

        latest_chapter = session.scalar(
            select(Chapter)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.chapter_number.desc(), Chapter.version.desc())
        )

        if latest_chapter is None:
            message = (
                f"Book ID {book.id} has no chapters yet. "
                "Run src.generate_chapter before checking the chapter gate."
            )
            print(message)
            send_email_notification(
                subject="Book generation paused: chapter missing",
                body=message,
            )
            return

        status = normalize_status(latest_chapter.chapter_notes_status)

        print(f"Book ID: {book.id}")
        print(f"Chapter ID: {latest_chapter.id}")
        print(f"Chapter number: {latest_chapter.chapter_number}")
        print(f"Chapter title: {latest_chapter.title}")
        print(f"Chapter version: {latest_chapter.version}")
        print(f"chapter_notes_status: {status or '(empty)'}")

        if status == "yes":
            if latest_chapter.chapter_notes:
                message = (
                    "Decision: Regenerate this chapter using chapter_notes, "
                    "then refresh its summary."
                )
                print(message)
                send_email_notification(
                    subject="Chapter notes received",
                    body=f"Chapter ID {latest_chapter.id}: {message}",
                )
            else:
                message = (
                    "Decision: Waiting for editor notes. "
                    "Add chapter_notes before regenerating this chapter."
                )
                print(message)
                send_email_notification(
                    subject="Waiting for chapter notes",
                    body=f"Chapter ID {latest_chapter.id}: {message}",
                )
            return

        if status == "no_notes_needed":
            message = "Decision: Chapter approved. Proceed to the next chapter."
            print(message)
            send_email_notification(
                subject="Chapter approved",
                body=f"Chapter ID {latest_chapter.id}: {message}",
            )
            return

        if status in {"", "no"}:
            message = (
                "Decision: Pipeline paused. Set chapter_notes_status to "
                "'yes' or 'no_notes_needed'."
            )
            print(message)
            send_email_notification(
                subject="Book generation paused: chapter status pending",
                body=f"Chapter ID {latest_chapter.id}: {message}",
            )
            return

        message = "Decision: Invalid status. Use one of: yes, no, no_notes_needed."
        print(message)
        send_email_notification(
            subject="Book generation paused: invalid chapter status",
            body=f"Chapter ID {latest_chapter.id}: {message}",
        )

    finally:
        session.close()


if __name__ == "__main__":
    check_chapter_gate_for_latest_book()
