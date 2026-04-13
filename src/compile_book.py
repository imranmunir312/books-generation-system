from pathlib import Path

from sqlalchemy import select

from src.db import get_session
from src.generate_chapter import get_latest_chapter_versions, normalize_status
from src.models import Book, Chapter
from src.notifications import send_email_notification


OUTPUT_DIR = Path("outputs")


def build_book_text(book: Book, chapters: list[Chapter]) -> str:
    parts = [f"# {book.title}", ""]

    if book.final_review_notes:
        parts.extend(
            [
                "## Final Review Notes Considered",
                "",
                book.final_review_notes.strip(),
                "",
            ]
        )

    for chapter in chapters:
        parts.extend(
            [
                f"## Chapter {chapter.chapter_number}: {chapter.title}",
                "",
                chapter.content.strip(),
                "",
            ]
        )

    return "\n".join(parts).strip() + "\n"


def compile_latest_book() -> None:
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
                subject="Final compilation paused: outline not approved",
                body=message,
            )
            return

        final_status = normalize_status(book.final_review_notes_status)
        can_compile = final_status == "no_notes_needed" or bool(book.final_review_notes)

        if not can_compile:
            message = (
                f"Book ID {book.id} is paused: set final_review_notes_status to "
                "'no_notes_needed' or add final_review_notes."
            )
            print(message)
            send_email_notification(
                subject="Final compilation paused: final review pending",
                body=message,
            )
            return

        all_chapters = list(
            session.scalars(
                select(Chapter)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.chapter_number.asc(), Chapter.version.desc())
            )
        )
        chapters = get_latest_chapter_versions(all_chapters)

        if not chapters:
            message = (
                f"Book ID {book.id} has no chapters yet. "
                "Run src.generate_chapter first."
            )
            print(message)
            send_email_notification(
                subject="Final compilation paused: chapters missing",
                body=message,
            )
            return

        unapproved = [
            chapter.chapter_number
            for chapter in chapters
            if normalize_status(chapter.chapter_notes_status) != "no_notes_needed"
        ]

        if unapproved:
            message = (
                "Book is paused: these chapters are not approved yet: "
                + ", ".join(str(number) for number in unapproved)
            )
            print(message)
            send_email_notification(
                subject="Final compilation paused: chapters need review",
                body=message,
            )
            return

        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = (OUTPUT_DIR / f"book_{book.id}_draft.txt").resolve()
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(build_book_text(book, chapters), encoding="utf-8")

        book.book_output_status = "compiled"
        book.output_file_path = str(output_path)
        session.commit()

        message = f"Compiled book draft: {output_path}"
        print(message)
        send_email_notification(
            subject="Final draft compiled",
            body=f"{message}\n\nBook ID: {book.id}\nTitle: {book.title}",
        )

    except Exception as error:
        session.rollback()
        send_email_notification(
            subject="Final compilation failed",
            body=f"Final compilation failed: {error}",
        )
        raise

    finally:
        session.close()


if __name__ == "__main__":
    compile_latest_book()
