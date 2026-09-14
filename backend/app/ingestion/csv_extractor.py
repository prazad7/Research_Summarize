from __future__ import annotations

import csv
from pathlib import Path

from app.db.models import Job
from app.ingestion.base import BaseExtractor, ExtractedContent
from app.ingestion.exceptions import CorruptFileError, NoExtractableTextError

_MAX_ROWS = 500  # keeps huge spreadsheets from blowing the LLM context


class CsvExtractor(BaseExtractor):
    def extract(self, job: Job) -> ExtractedContent:
        path = Path(job.stored_file_path)

        try:
            # utf-8-sig quietly strips a BOM if Excel added one on export;
            # errors="replace" keeps a handful of bad bytes from failing the
            # whole file rather than raising, since this is user data, not
            # something we control the encoding of.
            with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except (OSError, csv.Error) as exc:
            raise CorruptFileError(original=exc) from exc

        lines: list[str] = []
        for i, row in enumerate(rows):
            if i >= _MAX_ROWS:
                lines.append(f"... ({len(rows) - _MAX_ROWS} more rows truncated)")
                break
            # A blank field keeps its place in the row rather than being
            # dropped -- dropping it would shift every later value one
            # column to the left (e.g. a value from the last column ends
            # up looking like it belongs to the second-to-last one),
            # corrupting that row for anyone reading it by position.
            if any(c.strip() for c in row):
                lines.append(" | ".join(row))

        text = "\n".join(lines).strip()
        if not text:
            raise NoExtractableTextError()

        return ExtractedContent(
            text=text,
            title=path.stem,
            extra_metadata={"row_count": len(rows)},
        )
