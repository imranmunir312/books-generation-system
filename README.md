# Books Generation System

A small Python automation project for building an AI-assisted book generation workflow.

## Stack

- Python managed with `uv`
- Supabase Postgres as the database
- SQLAlchemy as the ORM
- `python-dotenv` for local environment variables
- Gemini API for AI generation
- Local Excel files for input
- SMTP email for notifications

## Setup

Install dependencies:

```bash
uv sync
```

Copy the environment example:

```bash
cp .env.example .env
```

Update `.env` with your real Supabase SQLAlchemy database URL:

```env
DATABASE_URL=postgresql+psycopg2://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@YOUR_POOLER_HOST:6543/postgres
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
EMAIL_NOTIFICATIONS_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=YOUR_EMAIL_ADDRESS
SMTP_PASSWORD=YOUR_EMAIL_APP_PASSWORD
SMTP_FROM_EMAIL=YOUR_EMAIL_ADDRESS
SMTP_TO_EMAIL=EDITOR_OR_YOUR_EMAIL_ADDRESS
```

For local development, prefer the Supabase pooler connection string because it avoids common IPv6/DNS issues with the direct database host.

For Gmail SMTP, use an app password instead of your normal account password.

## Verify

Check Python and imports:

```bash
uv run python --version
uv run python -c "import sqlalchemy; import dotenv; print('Setup working')"
```

Start the Gradio UI:

```bash
uv run python -m src.ui
```

In the UI, test from top to bottom:

- Step 1 imports the Excel file.
- Step 2 generates and approves the outline.
- Step 3 generates, approves, or regenerates chapters.
- Step 4 approves final review and compiles the draft.

Create a local Excel input template:

```bash
uv run python -m src.create_excel_template
```

Check the database connection without creating tables:

```bash
uv run python -m src.check_db
```

Create database tables:

```bash
uv run python -m src.main
```

Import books from local Excel:

```bash
uv run python -m src.import_books_from_excel
```

Generate an outline with Gemini for the latest book:

```bash
uv run python -m src.generate_outline
```

Check the outline review gate:

```bash
uv run python -m src.check_outline_gate
```

Generate the next chapter with Gemini:

```bash
uv run python -m src.generate_chapter
```

Check the latest chapter review gate:

```bash
uv run python -m src.check_chapter_gate
```

Regenerate the latest chapter after editor notes:

```bash
uv run python -m src.regenerate_chapter
```

Add final compilation fields to the existing `books` table:

```bash
uv run python -m src.migrate_final_fields
```

Compile the final book draft as a `.txt` file:

```bash
uv run python -m src.compile_book
```

## Local Excel Input

The preferred input source is a local `.xlsx` file.

Required columns:

- `title`
- `notes_on_outline_before`

The default importer reads:

```text
data/books_input.xlsx
```

## Email Notifications

Email notifications are handled in `src.notifications`.

Set this in `.env` to enable SMTP:

```env
EMAIL_NOTIFICATIONS_ENABLED=true
```

Test SMTP directly:

```bash
uv run python -m src.check_email
```

If you use `sandbox.smtp.mailtrap.io`, messages are captured in the Mailtrap sandbox inbox. They are not delivered to the real recipient inbox.

Notifications are sent for key events:

- Book input imported
- Outline ready or paused
- Waiting for outline notes
- Chapter ready or paused
- Waiting for chapter notes
- Final draft compiled
- Generation or compilation errors

## Current Database Models

The first table is `books`.

It stores:

- `title`
- `notes_on_outline_before`
- `status_outline_notes`
- `final_review_notes_status`
- `final_review_notes`
- `book_output_status`
- `output_file_path`
- timestamps

The second table is `outlines`.

It stores:

- `book_id`
- generated outline text
- optional editor notes after outline generation
- outline version
- timestamps

Outline generation is handled in `src.generate_outline`.

The outline review gate is handled in `src.check_outline_gate`.

The third table is `chapters`.

It stores:

- `book_id`
- chapter number and title
- chapter content
- chapter summary for context chaining
- chapter review notes/status
- version
- timestamps

Chapter generation is handled in `src.generate_chapter`.

The chapter review gate is handled in `src.check_chapter_gate`.

Chapter regeneration is handled in `src.regenerate_chapter`.

Final `.txt` compilation is handled in `src.compile_book`.
