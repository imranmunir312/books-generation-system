import os

from dotenv import load_dotenv
from google import genai
from sqlalchemy import select

from src.db import get_session
from src.models import Book, Chapter, Outline
from src.notifications import send_email_notification


MODEL_NAME = "gemini-2.5-flash"


def get_gemini_client() -> genai.Client:
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

    return genai.Client(api_key=api_key)


def normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def format_previous_summaries(chapters: list[Chapter]) -> str:
    summaries = [
        f"Chapter {chapter.chapter_number}: {chapter.summary}"
        for chapter in chapters
        if chapter.summary
    ]

    if not summaries:
        return "No previous chapters have been written yet."

    return "\n".join(summaries)


def get_latest_chapter_versions(chapters: list[Chapter]) -> list[Chapter]:
    latest_by_number: dict[int, Chapter] = {}

    for chapter in chapters:
        current = latest_by_number.get(chapter.chapter_number)

        if current is None or chapter.version > current.version:
            latest_by_number[chapter.chapter_number] = chapter

    return [
        latest_by_number[chapter_number]
        for chapter_number in sorted(latest_by_number)
    ]


def build_chapter_prompt(
    book: Book,
    outline: Outline,
    next_chapter_number: int,
    previous_chapters: list[Chapter],
) -> str:
    previous_context = format_previous_summaries(previous_chapters)

    return f"""
You are writing one chapter for a non-fiction book.

Book title:
{book.title}

Approved outline:
{outline.outline_text}

Previous chapter summaries:
{previous_context}

Task:
Write chapter {next_chapter_number}.

Requirements:
- Follow the approved outline.
- Use previous chapter summaries only as continuity context.
- Do not repeat previous chapters.
- Write in a clear, practical, reader-friendly style.
- Include examples where useful.
- Return the response in exactly this format:

CHAPTER_TITLE: <chapter title>
CHAPTER_CONTENT:
<full chapter content>
""".strip()


def parse_chapter_response(response_text: str, chapter_number: int) -> tuple[str, str]:
    title_marker = "CHAPTER_TITLE:"
    content_marker = "CHAPTER_CONTENT:"

    if title_marker not in response_text or content_marker not in response_text:
        return f"Chapter {chapter_number}", response_text.strip()

    title_part, content_part = response_text.split(content_marker, 1)
    title = title_part.replace(title_marker, "").strip()
    content = content_part.strip()

    return title or f"Chapter {chapter_number}", content


def summarize_chapter(client: genai.Client, chapter_content: str) -> str:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=f"""
Summarize this chapter for use as context when writing the next chapter.

Requirements:
- Keep it under 150 words.
- Capture the main ideas, examples, and continuity details.
- Do not add new information.

Chapter:
{chapter_content}
""".strip(),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty chapter summary.")

    return response.text.strip()


def generate_next_chapter_for_latest_book() -> None:
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
                subject="Chapter generation paused: outline not approved",
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
                subject="Chapter generation paused: outline missing",
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
        previous_chapters = get_latest_chapter_versions(all_chapters)
        next_chapter_number = (
            1
            if not previous_chapters
            else max(chapter.chapter_number for chapter in previous_chapters) + 1
        )

        client = get_gemini_client()
        chapter_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_chapter_prompt(
                book=book,
                outline=latest_outline,
                next_chapter_number=next_chapter_number,
                previous_chapters=previous_chapters,
            ),
        )

        if not chapter_response.text:
            raise RuntimeError("Gemini returned an empty chapter.")

        title, content = parse_chapter_response(
            chapter_response.text.strip(),
            next_chapter_number,
        )
        summary = summarize_chapter(client, content)

        chapter = Chapter(
            book_id=book.id,
            chapter_number=next_chapter_number,
            title=title[:255],
            content=content,
            summary=summary,
            chapter_notes_status="no",
            version=1,
        )

        session.add(chapter)
        session.commit()
        session.refresh(chapter)

        message = (
            f"Generated chapter ID {chapter.id} "
            f"(chapter {chapter.chapter_number}: {chapter.title}) "
            f"for book ID {book.id}."
        )
        print(message)
        send_email_notification(
            subject="Chapter ready for review",
            body=(
                f"{message}\n\nBook title: {book.title}\n\n"
                "Please review this chapter and update chapter_notes_status."
            ),
        )

    except Exception as error:
        session.rollback()
        send_email_notification(
            subject="Chapter generation failed",
            body=f"Chapter generation failed: {error}",
        )
        raise

    finally:
        session.close()


if __name__ == "__main__":
    generate_next_chapter_for_latest_book()
