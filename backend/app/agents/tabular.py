"""Deterministic filter/count/list execution for chat questions about
tabular content (Excel/CSV).

Why this exists: a single LLM call asked to count or filter dozens of rows
by reading them is unreliable -- it approximates rather than computes, and
prompt wording (enumerate-before-answering, temperature=0) doesn't fix that
(confirmed empirically: both still undercounted on a real 50-row file).
The fix here keeps the existing architecture and its bounds completely
unchanged (same `extracted_text` used everywhere else, same row/char caps
already applied at extraction time, no new dependency, no re-reading the
original file) -- it only replaces "ask the LLM to eyeball-count" with:
    1. ask the LLM to translate the question into a small structured
       filter spec against the table's REAL column names (still one cheap
       LLM call, using structured output the same way the summarization
       crew already does via `output_pydantic`)
    2. execute that spec with plain Python -- exact, not approximate
    3. ask the LLM only to phrase the already-computed result in natural
       language; it never recomputes or overrides the number

Scanning the full original file for very large uploads (rather than this
same bounded, already-extracted text) is a deliberately separate, later
concern -- out of scope here by design.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.logging_config import get_logger

logger = get_logger(__name__)

_LIST_PREVIEW_CAP = 30  # keeps a "list" reply readable even if hundreds of rows match


class ColumnFilter(BaseModel):
    column: str = Field(description="An exact column/header name copied from the table's real columns")
    op: Literal["equals", "not_equals", "contains", "greater_than", "less_than"] = "equals"
    value: str


class TabularQuerySpec(BaseModel):
    applicable: bool = Field(
        description="True ONLY if the question can be fully answered by filtering this "
        "table's rows on simple per-column conditions and then counting or listing them. "
        "False for anything else: summaries, trends, averages/sums, opinions, comparisons "
        "not expressible as simple per-column conditions, or questions unrelated to this table."
    )
    filters: list[ColumnFilter] = Field(default_factory=list)
    action: Literal["count", "list"] = "count"


def parse_table(extracted_text: str) -> list[dict[str, str]]:
    """Reconstructs structured rows from the extractor's own flattened
    '## Sheet: X' + header-then-' | '-joined-rows text (see
    excel_extractor.py / csv_extractor.py). Returns [] if nothing
    recognizably tabular is found."""
    rows: list[dict[str, str]] = []
    header: list[str] | None = None

    for raw_line in extracted_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## Sheet:") or line.startswith("..."):
            header = None  # each sheet/truncation marker starts a fresh header search
            continue

        fields = [f.strip() for f in line.split("|")]
        if header is None:
            header = fields
            continue
        if len(fields) != len(header):
            continue  # defensive: skip anything that doesn't line up with its header

        rows.append(dict(zip(header, fields)))

    return rows


def _find_column(row: dict[str, str], name: str) -> str | None:
    target = name.strip().lower()
    for key in row:
        if key.strip().lower() == target:
            return key
    return None


def _as_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _row_matches(row: dict[str, str], filters: list[ColumnFilter]) -> bool:
    for f in filters:
        col_key = _find_column(row, f.column)
        if col_key is None:
            return False
        cell = row.get(col_key, "").strip()
        cell_lower = cell.lower()
        val_lower = f.value.strip().lower()

        if f.op == "equals" and cell_lower != val_lower:
            return False
        if f.op == "not_equals" and cell_lower == val_lower:
            return False
        if f.op == "contains" and val_lower not in cell_lower:
            return False
        if f.op in ("greater_than", "less_than"):
            cell_num, val_num = _as_float(cell), _as_float(f.value)
            if cell_num is None or val_num is None:
                # Not numeric -- fall back to lexicographic comparison, which
                # works correctly for ISO-formatted dates (e.g. 2025-05-23).
                cell_num_ok = cell < f.value if f.op == "less_than" else cell > f.value
                if not cell_num_ok:
                    return False
            elif f.op == "greater_than" and not (cell_num > val_num):
                return False
            elif f.op == "less_than" and not (cell_num < val_num):
                return False
    return True


def _unknown_columns(rows: list[dict[str, str]], filters: list[ColumnFilter]) -> list[str]:
    if not rows:
        return [f.column for f in filters]
    sample = rows[0]
    return [f.column for f in filters if _find_column(sample, f.column) is None]


def try_answer_tabular_question(
    rows: list[dict[str, str]], user_message: str
) -> tuple[bool, str | None]:
    """Returns (handled, computed_result_text).

    handled=False means this question isn't a simple per-column
    filter/count/list question (or the table couldn't be parsed, or the
    LLM referenced a column that doesn't actually exist) -- the caller
    should fall back to the normal free-text-grounded chat reply rather
    than risk presenting a confidently wrong computed answer.
    """
    if not rows:
        return False, None

    columns = list(rows[0].keys())
    classify_prompt = (
        "This table has exactly these columns: " + ", ".join(columns) + ".\n\n"
        "Convert the question below into a structured filter spec using ONLY column names "
        "from that exact list (copy them verbatim, including case) -- but only if the "
        "question can be fully answered by filtering rows on simple per-column conditions "
        "and then counting or listing them. Otherwise, set applicable to false.\n\n"
        f"Question: {user_message}"
    )

    llm = get_llm(temperature=0.0)
    try:
        spec = llm.call([{"role": "user", "content": classify_prompt}], response_model=TabularQuerySpec)
    except Exception:
        logger.warning("tabular_query_classification_failed", exc_info=True)
        return False, None

    if not isinstance(spec, TabularQuerySpec) or not spec.applicable:
        return False, None

    bad_columns = _unknown_columns(rows, spec.filters)
    if bad_columns:
        # The LLM referenced a column that isn't actually in the table --
        # rather than silently compute against a filter that can never
        # match anything, fall back to the free-text reply so the user
        # gets a real (if less precise) answer instead of a confident "0".
        logger.warning("tabular_query_unknown_columns", columns=bad_columns)
        return False, None

    matches = [r for r in rows if _row_matches(r, spec.filters)]

    if spec.action == "count":
        return True, f"The exact count, computed from every matching row, is {len(matches)}."

    preview = matches[:_LIST_PREVIEW_CAP]
    lines = [" | ".join(f"{k}: {v}" for k, v in r.items()) for r in preview]
    result = f"There are exactly {len(matches)} matching row(s). The full list:\n" + "\n".join(lines)
    if len(matches) > _LIST_PREVIEW_CAP:
        result += f"\n... and {len(matches) - _LIST_PREVIEW_CAP} more matching row(s) not shown here."
    return True, result
