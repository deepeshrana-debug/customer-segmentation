import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import docx  # noqa: E402

from summary import document_kind, parse_list, read_document  # noqa: E402


def make_docx(paragraphs: list[str], rows: list[tuple[str, str]] | None = None) -> bytes:
    document = docx.Document()
    for line in paragraphs:
        document.add_paragraph(line)

    if rows:
        table = document.add_table(rows=0, cols=2)
        for left, right in rows:
            cells = table.add_row().cells
            cells[0].text = left
            cells[1].text = right

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_document_kind():
    assert document_kind("numbers.docx") == "word"
    assert document_kind("REPORT.PDF") == "pdf"
    assert document_kind("notes.txt") == "text"
    assert document_kind("photo.png") is None


def test_unsupported_file_gets_a_plain_message():
    result = read_document("photo.png", b"abc")
    assert "Word file" in result["error"]


def test_empty_document_is_reported():
    result = read_document("notes.txt", b"   ")
    assert "empty" in result["error"].lower()


def test_text_file_is_read():
    text = (
        "Total buyers: 1,000\n"
        "Most buyers: 233\n"
        "Regular buyers: 433\n"
        "Least buyers: 334\n"
    )
    result = read_document("numbers.txt", text.encode("utf-8"))

    assert result["error"] is None
    assert result["values"]["total"] == 1000
    assert result["values"]["most"] == 233
    assert result["values"]["regular"] == 433


def test_text_file_with_commas_is_read():
    result = read_document("numbers.txt", b"Total buyers: 1,000\nMost buyers: 233\n")
    assert result["values"]["most"] == 233


def test_document_with_no_numbers_says_so():
    result = read_document("notes.txt", b"Dear sir, here is my weekly summary.\n")
    assert result["error"] is not None
    assert result["values"] == {}


def test_word_paragraphs_are_read():
    data = make_docx([
        "Buyer report",
        "Most buyers: 233",
        "Regular buyers: 433",
        "Least buyers: 334",
        "Total buyers: 1000",
    ])
    result = read_document("report.docx", data)

    assert result["error"] is None
    assert result["values"] == {
        "most": 233, "regular": 433, "least": 334, "total": 1000,
    }
    assert result["missing"] == [
        "frequent", "last_month", "big_spenders",
    ]


def test_word_table_is_read():
    data = make_docx([], rows=[("Most buyers", "233"), ("Total buyers", "1000")])
    result = read_document("report.docx", data)

    assert result["error"] is None
    assert result["values"]["most"] == 233
    assert result["values"]["total"] == 1000


def test_word_file_with_other_numbers_ignored():
    data = make_docx(["Our shop opened in 2019.", "Most buyers: 233"])
    result = read_document("report.docx", data)
    assert result["values"] == {"most": 233}


def test_a_broken_word_file_does_not_crash():
    result = read_document("broken.docx", b"this is not a real docx")
    assert result["error"] is not None
    assert "could not be read" in result["error"].lower()


def test_name_and_number_on_separate_lines():
    text = "Most buyers\n233\nRegular buyers\n433\n"
    result = read_document("layout.txt", text.encode("utf-8"))

    assert result["values"]["most"] == 233
    assert result["values"]["regular"] == 433


def test_document_and_list_parser_agree():
    text = "Most buyers: 233\nLeast buyers: 334"
    from_document = read_document("n.txt", text.encode("utf-8"))["values"]
    from_list, _unknown = parse_list(text)
    assert from_document == from_list


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
