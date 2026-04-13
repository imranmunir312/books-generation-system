from sqlalchemy import text

from src.db import engine


def migrate_final_fields() -> None:
    statements = [
        """
        ALTER TABLE books
        ADD COLUMN IF NOT EXISTS final_review_notes_status VARCHAR(50) NOT NULL DEFAULT 'no'
        """,
        """
        ALTER TABLE books
        ADD COLUMN IF NOT EXISTS final_review_notes TEXT
        """,
        """
        ALTER TABLE books
        ADD COLUMN IF NOT EXISTS book_output_status VARCHAR(50) NOT NULL DEFAULT 'not_ready'
        """,
        """
        ALTER TABLE books
        ADD COLUMN IF NOT EXISTS output_file_path VARCHAR(500)
        """,
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    print("Final compilation fields are ready on books table.")


if __name__ == "__main__":
    migrate_final_fields()
