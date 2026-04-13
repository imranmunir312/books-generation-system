import io
from contextlib import redirect_stdout
from pathlib import Path

import gradio as gr
from sqlalchemy import select

from src.compile_book import compile_latest_book
from src.db import get_session
from src.generate_chapter import generate_next_chapter_for_latest_book
from src.generate_outline import generate_outline_for_latest_book
from src.import_books_from_excel import import_books_from_excel
from src.models import Book, Chapter, Outline
from src.regenerate_chapter import regenerate_latest_chapter_for_latest_book


def capture_output(action) -> str:
    buffer = io.StringIO()

    try:
        with redirect_stdout(buffer):
            action()
    except Exception as error:
        return f"{buffer.getvalue()}\nError: {error}".strip()

    return buffer.getvalue().strip() or "Done."


def get_latest_book(session) -> Book | None:
    return session.scalar(select(Book).order_by(Book.id.desc()))


def get_latest_outline(session, book_id: int) -> Outline | None:
    return session.scalar(
        select(Outline)
        .where(Outline.book_id == book_id)
        .order_by(Outline.version.desc())
    )


def get_latest_chapter(session, book_id: int) -> Chapter | None:
    return session.scalar(
        select(Chapter)
        .where(Chapter.book_id == book_id)
        .order_by(Chapter.chapter_number.desc(), Chapter.version.desc())
    )


def latest_state() -> tuple[Book | None, Outline | None, Chapter | None]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return None, None, None

        outline = get_latest_outline(session, book.id)
        chapter = get_latest_chapter(session, book.id)

        return book, outline, chapter

    finally:
        session.close()


def refresh_status() -> str:
    book, outline, chapter = latest_state()

    if book is None:
        return (
            "No book found yet.\n\n"
            "Start with Step 1: upload/import a local Excel file."
        )

    lines = [
        f"Book: {book.title} (ID {book.id})",
        f"Outline review: {book.status_outline_notes}",
        f"Final review: {book.final_review_notes_status}",
        f"Output status: {book.book_output_status}",
    ]

    if outline:
        lines.append(f"Latest outline: version {outline.version} (ID {outline.id})")
    else:
        lines.append("Latest outline: not generated")

    if chapter:
        lines.extend(
            [
                f"Latest chapter: {chapter.chapter_number} - {chapter.title}",
                f"Chapter review: {chapter.chapter_notes_status}",
                f"Chapter version: {chapter.version}",
            ]
        )
    else:
        lines.append("Latest chapter: not generated")

    lines.append(f"Output file: {book.output_file_path or 'not compiled'}")

    return "\n".join(lines)


def next_step_hint() -> str:
    book, outline, chapter = latest_state()

    if book is None:
        return "Next: Import a local Excel file in Step 1."

    if outline is None:
        return "Next: Click 'Generate Outline' in Step 2."

    if book.status_outline_notes != "no_notes_needed":
        return "Next: Review the outline, then click 'Approve Outline'."

    if chapter is None:
        return "Next: Click 'Generate Next Chapter' in Step 3."

    if chapter.chapter_notes_status == "yes" and chapter.chapter_notes:
        return "Next: Click 'Regenerate Latest Chapter' in Step 3."

    if chapter.chapter_notes_status != "no_notes_needed":
        return "Next: Review the latest chapter, then approve it or request changes."

    if book.final_review_notes_status != "no_notes_needed":
        return (
            "Next: Either generate another chapter in Step 3, or approve final "
            "review in Step 4 and compile."
        )

    return "Next: Click 'Compile Final Draft' in Step 4."


def refresh_previews() -> tuple[str, str, str, str]:
    book, outline, chapter = latest_state()

    outline_preview = (
        outline.outline_text
        if outline
        else "No outline generated yet."
    )
    chapter_preview = (
        chapter.content
        if chapter
        else "No chapter generated yet."
    )
    summary_preview = (
        chapter.summary
        if chapter and chapter.summary
        else "No chapter summary generated yet."
    )
    final_preview = "No final draft compiled yet."

    if book and book.output_file_path:
        output_path = Path(book.output_file_path).resolve()

        if output_path.exists():
            final_preview = output_path.read_text(encoding="utf-8")

    return outline_preview, chapter_preview, summary_preview, final_preview


def dashboard_outputs() -> tuple[str, str, str, str, str, str]:
    outline_preview, chapter_preview, summary_preview, final_preview = refresh_previews()

    return (
        refresh_status(),
        next_step_hint(),
        outline_preview,
        chapter_preview,
        summary_preview,
        final_preview,
    )


def refresh_dashboard() -> tuple[str, str, str, str, str, str]:
    return dashboard_outputs()


def import_excel_input(excel_file) -> tuple[str, str, str, str, str, str, str]:
    if excel_file is None:
        return (
            "Please upload a local Excel .xlsx file.",
            *dashboard_outputs(),
        )

    file_path = getattr(excel_file, "name", None) or str(excel_file)
    output = capture_output(lambda: import_books_from_excel(file_path))

    return output, *dashboard_outputs()


def run_generate_outline() -> tuple[str, str, str, str, str, str, str]:
    output = capture_output(generate_outline_for_latest_book)

    return output, *dashboard_outputs()


def approve_outline() -> tuple[str, str, str, str, str, str, str]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return "No book found.", *dashboard_outputs()

        if get_latest_outline(session, book.id) is None:
            return (
                "No outline found. Generate an outline first.",
                *dashboard_outputs(),
            )

        book.status_outline_notes = "no_notes_needed"
        session.commit()

        return (
            "Outline approved. You can now generate chapters.",
            *dashboard_outputs(),
        )

    except Exception as error:
        session.rollback()
        return f"Error: {error}", *dashboard_outputs()

    finally:
        session.close()


def request_outline_changes(notes: str) -> tuple[str, str, str, str, str, str, str]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return "No book found.", *dashboard_outputs()

        outline = get_latest_outline(session, book.id)

        if outline is None:
            return (
                "No outline found. Generate an outline first.",
                *dashboard_outputs(),
            )

        if not notes.strip():
            return (
                "Add outline change notes first.",
                *dashboard_outputs(),
            )

        book.status_outline_notes = "yes"
        outline.notes_on_outline_after = notes.strip()
        session.commit()

        output = capture_output(generate_outline_for_latest_book)

        return output, *dashboard_outputs()

    except Exception as error:
        session.rollback()
        return f"Error: {error}", *dashboard_outputs()

    finally:
        session.close()


def run_generate_chapter() -> tuple[str, str, str, str, str, str, str]:
    output = capture_output(generate_next_chapter_for_latest_book)

    return output, *dashboard_outputs()


def approve_chapter() -> tuple[str, str, str, str, str, str, str]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return "No book found.", *dashboard_outputs()

        chapter = get_latest_chapter(session, book.id)

        if chapter is None:
            return (
                "No chapter found. Generate a chapter first.",
                *dashboard_outputs(),
            )

        chapter.chapter_notes_status = "no_notes_needed"
        chapter.chapter_notes = None
        session.commit()

        return "Latest chapter approved.", *dashboard_outputs()

    except Exception as error:
        session.rollback()
        return f"Error: {error}", *dashboard_outputs()

    finally:
        session.close()


def request_chapter_changes(notes: str) -> tuple[str, str, str, str, str, str, str]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return "No book found.", *dashboard_outputs()

        chapter = get_latest_chapter(session, book.id)

        if chapter is None:
            return (
                "No chapter found. Generate a chapter first.",
                *dashboard_outputs(),
            )

        if not notes.strip():
            return (
                "Add chapter change notes first.",
                *dashboard_outputs(),
            )

        chapter.chapter_notes_status = "yes"
        chapter.chapter_notes = notes.strip()
        session.commit()

        return (
            "Chapter change request saved. Click regenerate next.",
            *dashboard_outputs(),
        )

    except Exception as error:
        session.rollback()
        return f"Error: {error}", *dashboard_outputs()

    finally:
        session.close()


def run_regenerate_chapter() -> tuple[str, str, str, str, str, str, str]:
    output = capture_output(regenerate_latest_chapter_for_latest_book)

    return output, *dashboard_outputs()


def approve_final_review() -> tuple[str, str, str, str, str, str, str]:
    session = get_session()

    try:
        book = get_latest_book(session)

        if book is None:
            return "No book found.", *dashboard_outputs()

        book.final_review_notes_status = "no_notes_needed"
        session.commit()

        return "Final review approved.", *dashboard_outputs()

    except Exception as error:
        session.rollback()
        return f"Error: {error}", *dashboard_outputs()

    finally:
        session.close()


def run_compile_book() -> tuple[str, str, str, str, str, str, str, str | None]:
    output = capture_output(compile_latest_book)
    file_path = None

    session = get_session()

    try:
        book = get_latest_book(session)

        if book and book.output_file_path:
            output_path = Path(book.output_file_path).resolve()

            if output_path.exists():
                file_path = str(output_path)

    finally:
        session.close()

    return output, *dashboard_outputs(), file_path


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Book Generation System") as app:
        gr.Markdown(
            """
            # Book Generation System

            Use this page from top to bottom. Each step updates Supabase and shows
            what you should do next.
            """
        )

        with gr.Row():
            status_box = gr.Textbox(
                label="Current State",
                value=refresh_status(),
                lines=10,
                interactive=False,
            )
            next_box = gr.Textbox(
                label="What To Do Next",
                value=next_step_hint(),
                lines=10,
                interactive=False,
            )

        action_output = gr.Textbox(label="Last Action Result", lines=8)
        with gr.Accordion("Generated Content Preview", open=True):
            outline_preview_box = gr.Textbox(
                label="Latest Generated Outline",
                value=refresh_previews()[0],
                lines=12,
                interactive=False,
            )
            chapter_preview_box = gr.Textbox(
                label="Latest Generated Chapter",
                value=refresh_previews()[1],
                lines=16,
                interactive=False,
            )
            chapter_summary_box = gr.Textbox(
                label="Latest Chapter Summary Used As Context",
                value=refresh_previews()[2],
                lines=5,
                interactive=False,
            )
            final_preview_box = gr.Textbox(
                label="Compiled Draft Preview",
                value=refresh_previews()[3],
                lines=16,
                interactive=False,
            )

        dashboard_targets = [
            status_box,
            next_box,
            outline_preview_box,
            chapter_preview_box,
            chapter_summary_box,
            final_preview_box,
        ]
        action_targets = [action_output, *dashboard_targets]
        refresh_button = gr.Button("Refresh")
        refresh_button.click(refresh_dashboard, outputs=dashboard_targets)

        gr.Markdown("## Step 1: Import Book Input")
        gr.Markdown(
            "Upload an Excel file with columns: `title`, `notes_on_outline_before`."
        )
        excel_input = gr.File(label="Local Excel file", file_types=[".xlsx"])
        import_button = gr.Button("1. Import Excel")
        import_button.click(
            import_excel_input,
            inputs=excel_input,
            outputs=action_targets,
        )

        gr.Markdown("## Step 2: Generate And Review Outline")
        with gr.Row():
            generate_outline_button = gr.Button("2A. Generate Outline")
            approve_outline_button = gr.Button("2B. Approve Outline")
        outline_change_notes = gr.Textbox(
            label="Outline change notes, only if you want regeneration",
            lines=3,
        )
        request_outline_button = gr.Button("Request Outline Changes And Regenerate")
        generate_outline_button.click(
            run_generate_outline,
            outputs=action_targets,
        )
        approve_outline_button.click(
            approve_outline,
            outputs=action_targets,
        )
        request_outline_button.click(
            request_outline_changes,
            inputs=outline_change_notes,
            outputs=action_targets,
        )

        gr.Markdown("## Step 3: Generate And Review Chapters")
        with gr.Row():
            generate_chapter_button = gr.Button("3A. Generate Next Chapter")
            approve_chapter_button = gr.Button("3B. Approve Latest Chapter")
        chapter_change_notes = gr.Textbox(
            label="Chapter change notes, only if you want regeneration",
            lines=3,
        )
        with gr.Row():
            request_chapter_button = gr.Button("Request Chapter Changes")
            regenerate_chapter_button = gr.Button("Regenerate Latest Chapter")
        generate_chapter_button.click(
            run_generate_chapter,
            outputs=action_targets,
        )
        approve_chapter_button.click(
            approve_chapter,
            outputs=action_targets,
        )
        request_chapter_button.click(
            request_chapter_changes,
            inputs=chapter_change_notes,
            outputs=action_targets,
        )
        regenerate_chapter_button.click(
            run_regenerate_chapter,
            outputs=action_targets,
        )

        gr.Markdown("## Step 4: Final Review And Compile")
        with gr.Row():
            approve_final_button = gr.Button("4A. Approve Final Review")
            compile_button = gr.Button("4B. Compile Final Draft")
        gr.Markdown(
            "After compilation, use the file link below to download the `.txt` draft."
        )
        final_file = gr.File(label="Compiled Draft")
        approve_final_button.click(
            approve_final_review,
            outputs=action_targets,
        )
        compile_button.click(
            run_compile_book,
            outputs=[*action_targets, final_file],
        )

    return app


if __name__ == "__main__":
    build_ui().launch()
