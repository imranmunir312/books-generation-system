import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Add it to your .env file.")

if DATABASE_URL.startswith("DATABASE_URL="):
    raise RuntimeError(
        "DATABASE_URL value is invalid. In .env, use DATABASE_URL=<postgres-url> only once."
    )

if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg2://")):
    raise RuntimeError(
        "DATABASE_URL must start with postgresql:// or postgresql+psycopg2://."
    )

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    echo=False,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """Create a short-lived database session for scripts."""
    return SessionLocal()
