from src.db import engine


def check_database_connection() -> None:
    with engine.connect() as connection:
        result = connection.exec_driver_sql("select 1").scalar()

    if result != 1:
        raise RuntimeError("Database check failed.")

    print("Database connection working.")


if __name__ == "__main__":
    check_database_connection()
