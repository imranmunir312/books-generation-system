from sqlalchemy import select

from src.db import get_session
from src.models import Book, Outline
from src.notifications import send_email_notification


def normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def check_outline_gate_for_latest_book() -> None:
    session = get_session()

    try:
        book = session.scalar(select(Book).order_by(Book.id.desc()))

        if book is None:
            raise RuntimeError("No book found. Import a book from Excel first.")

        latest_outline = session.scalar(
            select(Outline)
            .where(Outline.book_id == book.id)
            .order_by(Outline.version.desc())
        )

        if latest_outline is None:
            message = (
                f"Book ID {book.id} has no outline yet. "
                "Run src.generate_outline before checking the outline gate."
            )
            print(message)
            send_email_notification(
                subject="Book generation paused: outline missing",
                body=message,
            )
            return

        status = normalize_status(book.status_outline_notes)

        print(f"Book ID: {book.id}")
        print(f"Outline ID: {latest_outline.id}")
        print(f"Outline version: {latest_outline.version}")
        print(f"status_outline_notes: {status or '(empty)'}")

        if status == "yes":
            if latest_outline.notes_on_outline_after:
                message = (
                    "Decision: Regenerate outline using notes_on_outline_after, "
                    "then create a new outline version."
                )
                print(message)
                send_email_notification(
                    subject="Outline notes received",
                    body=f"Book ID {book.id}: {message}",
                )
            else:
                message = (
                    "Decision: Waiting for editor notes. "
                    "Add notes_on_outline_after before regenerating."
                )
                print(message)
                send_email_notification(
                    subject="Waiting for outline notes",
                    body=f"Book ID {book.id}: {message}",
                )
            return

        if status == "no_notes_needed":
            message = "Decision: Outline approved. Proceed to chapter generation."
            print(message)
            send_email_notification(
                subject="Outline approved",
                body=f"Book ID {book.id}: {message}",
            )
            return

        if status in {"", "no"}:
            message = (
                "Decision: Pipeline paused. Set status_outline_notes to "
                "'yes' or 'no_notes_needed'."
            )
            print(message)
            send_email_notification(
                subject="Book generation paused: outline status pending",
                body=f"Book ID {book.id}: {message}",
            )
            return

        message = "Decision: Invalid status. Use one of: yes, no, no_notes_needed."
        print(message)
        send_email_notification(
            subject="Book generation paused: invalid outline status",
            body=f"Book ID {book.id}: {message}",
        )

    finally:
        session.close()


if __name__ == "__main__":
    check_outline_gate_for_latest_book()
