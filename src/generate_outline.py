import os

from dotenv import load_dotenv
from google import genai
from sqlalchemy import select

from src.db import get_session
from src.models import Book, Outline
from src.notifications import send_email_notification


MODEL_NAME = "gemini-2.5-flash"


def build_outline_prompt(book: Book) -> str:
    return f"""
You are helping create a structured non-fiction book outline.

Book title:
{book.title}

Editor notes before outline generation:
{book.notes_on_outline_before}

Create a clear, practical outline for this book.

Requirements:
- Include 5 to 8 chapters.
- For each chapter, include a chapter title and 3 to 5 bullet points.
- Keep the outline specific to the title and editor notes.
- Do not write full chapters yet.
""".strip()


def generate_outline_text(book: Book) -> str:
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_outline_prompt(book),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty outline.")

    return response.text.strip()


def generate_outline_for_latest_book() -> None:
    session = get_session()

    try:
        book = session.scalar(select(Book).order_by(Book.id.desc()))

        if book is None:
            raise RuntimeError("No book found. Import a book from Excel first.")

        if not book.notes_on_outline_before:
            message = (
                f"Book ID {book.id} is paused: notes_on_outline_before is required."
            )
            print(message)
            send_email_notification(
                subject="Book generation paused: outline notes missing",
                body=message,
            )
            return

        outline_text = generate_outline_text(book)
        latest_outline = session.scalar(
            select(Outline)
            .where(Outline.book_id == book.id)
            .order_by(Outline.version.desc())
        )
        next_version = 1 if latest_outline is None else latest_outline.version + 1

        outline = Outline(
            book_id=book.id,
            outline_text=outline_text,
            version=next_version,
        )

        session.add(outline)
        session.commit()
        session.refresh(outline)

        message = (
            f"Generated outline ID {outline.id} for book ID {book.id} "
            f"(version {outline.version})."
        )
        print(message)
        send_email_notification(
            subject="Outline ready for review",
            body=(
                f"{message}\n\nBook title: {book.title}\n\n"
                "Please review the outline and update status_outline_notes."
            ),
        )

    except Exception as error:
        session.rollback()
        send_email_notification(
            subject="Outline generation failed",
            body=f"Outline generation failed: {error}",
        )
        raise

    finally:
        session.close()


if __name__ == "__main__":
    generate_outline_for_latest_book()
