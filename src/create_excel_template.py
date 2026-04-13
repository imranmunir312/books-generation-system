from pathlib import Path

from openpyxl import Workbook


def create_excel_template() -> None:
    output_path = Path("data/books_input.xlsx")
    output_path.parent.mkdir(exist_ok=True)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "books"
    worksheet.append(["title", "notes_on_outline_before"])
    worksheet.append(
        [
            "The Future of AI in Education",
            "Make it practical, beginner-friendly, and focused on classroom examples.",
        ]
    )
    workbook.save(output_path)

    print(f"Created Excel input template: {output_path}")


if __name__ == "__main__":
    create_excel_template()
