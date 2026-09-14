import pytest

from app.db.models import ContentType, Job, JobStatus
from app.ingestion.csv_extractor import CsvExtractor
from app.ingestion.exceptions import NoExtractableTextError


def _make_job(path: str) -> Job:
    return Job(
        id="test-job",
        status=JobStatus.PENDING,
        content_type=ContentType.CSV,
        source_type="file",
        source_reference="data.csv",
        stored_file_path=path,
    )


def test_csv_extractor_reads_rows(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Name,Age,City\nAlice,30,NYC\nBob,25,LA\n", encoding="utf-8")

    extracted = CsvExtractor().extract(_make_job(str(csv_path)))

    assert "Name | Age | City" in extracted.text
    assert "Alice | 30 | NYC" in extracted.text
    assert extracted.title == "data"
    assert extracted.extra_metadata["row_count"] == 3


def test_csv_extractor_strips_bom(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_bytes("Name,Age\nAlice,30\n".encode("utf-8-sig"))

    extracted = CsvExtractor().extract(_make_job(str(csv_path)))

    assert extracted.text.startswith("Name | Age")


def test_csv_extractor_raises_on_empty_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(NoExtractableTextError):
        CsvExtractor().extract(_make_job(str(csv_path)))


def test_csv_extractor_keeps_column_alignment_when_a_middle_field_is_blank(tmp_path):
    """Same regression as the Excel extractor: a blank middle field (Phone)
    must stay an empty field, not be dropped -- otherwise City shifts left
    into Phone's position for that row and breaks positional reads."""
    csv_path = tmp_path / "students.csv"
    csv_path.write_text(
        "Name,Phone,Course,City\nAlice,9876543210,python,Chennai\nBob,,python,Chennai\n",
        encoding="utf-8",
    )

    extracted = CsvExtractor().extract(_make_job(str(csv_path)))

    lines = extracted.text.splitlines()
    alice_line = next(line for line in lines if line.startswith("Alice"))
    bob_line = next(line for line in lines if line.startswith("Bob"))

    assert alice_line.count("|") == bob_line.count("|") == 3
    assert bob_line.split("|")[-1].strip() == "Chennai"


def test_csv_extractor_truncates_large_files(tmp_path):
    csv_path = tmp_path / "big.csv"
    rows = "\n".join(f"row{i},{i}" for i in range(600))
    csv_path.write_text(rows, encoding="utf-8")

    extracted = CsvExtractor().extract(_make_job(str(csv_path)))

    assert "more rows truncated" in extracted.text
