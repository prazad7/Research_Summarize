from app.agents.tabular import (
    ColumnFilter,
    TabularQuerySpec,
    parse_table,
    try_answer_tabular_question,
)

_SAMPLE_TEXT = """## Sheet: Sheet1
Name | Phone | Course | City
Alice | 9876543210 | python | Chennai
Bob |  | python | chennai
Carol | 9123456789 | ml | CHENNAI
Dave | 9000011111 | python | Salem"""


def test_parse_table_reconstructs_rows_with_blank_fields_kept():
    rows = parse_table(_SAMPLE_TEXT)

    assert len(rows) == 4
    assert rows[0] == {"Name": "Alice", "Phone": "9876543210", "Course": "python", "City": "Chennai"}
    # Bob's blank Phone must stay an empty field, not disappear.
    assert rows[1] == {"Name": "Bob", "Phone": "", "Course": "python", "City": "chennai"}


def test_parse_table_resets_header_per_sheet_and_skips_truncation_marker():
    text = (
        "## Sheet: A\n"
        "Name | City\n"
        "Alice | Chennai\n"
        "... (5 more rows truncated)\n"
        "## Sheet: B\n"
        "Product | Price\n"
        "Widget | 10"
    )

    rows = parse_table(text)

    assert rows == [
        {"Name": "Alice", "City": "Chennai"},
        {"Product": "Widget", "Price": "10"},
    ]


def test_parse_table_returns_empty_for_non_tabular_text():
    assert parse_table("Just a plain paragraph of prose, no pipes here at all.") == []


def test_try_answer_tabular_question_computes_exact_count(mocker):
    rows = parse_table(_SAMPLE_TEXT)
    spec = TabularQuerySpec(
        applicable=True,
        filters=[ColumnFilter(column="City", op="equals", value="chennai")],
        action="count",
    )
    mocker.patch("app.agents.tabular.get_llm").return_value.call.return_value = spec

    handled, result = try_answer_tabular_question(rows, "how many are from chennai")

    assert handled is True
    # Case-insensitive match across "Chennai" / "chennai" / "CHENNAI" -> 3, not 2.
    assert "3" in result


def test_try_answer_tabular_question_lists_matches(mocker):
    rows = parse_table(_SAMPLE_TEXT)
    spec = TabularQuerySpec(
        applicable=True,
        filters=[ColumnFilter(column="Course", op="equals", value="python")],
        action="list",
    )
    mocker.patch("app.agents.tabular.get_llm").return_value.call.return_value = spec

    handled, result = try_answer_tabular_question(rows, "list students taking python")

    assert handled is True
    assert "Alice" in result
    assert "Bob" in result
    assert "Dave" in result
    assert "Carol" not in result  # Carol's course is "ml", not "python"


def test_try_answer_tabular_question_falls_back_when_not_applicable(mocker):
    rows = parse_table(_SAMPLE_TEXT)
    spec = TabularQuerySpec(applicable=False)
    mocker.patch("app.agents.tabular.get_llm").return_value.call.return_value = spec

    handled, result = try_answer_tabular_question(rows, "summarize the overall trend")

    assert handled is False
    assert result is None


def test_try_answer_tabular_question_falls_back_on_unknown_column(mocker):
    rows = parse_table(_SAMPLE_TEXT)
    spec = TabularQuerySpec(
        applicable=True,
        filters=[ColumnFilter(column="Country", op="equals", value="India")],  # not a real column
        action="count",
    )
    mocker.patch("app.agents.tabular.get_llm").return_value.call.return_value = spec

    handled, result = try_answer_tabular_question(rows, "how many from India")

    assert handled is False
    assert result is None


def test_try_answer_tabular_question_falls_back_when_no_rows(mocker):
    handled, result = try_answer_tabular_question([], "how many from chennai")

    assert handled is False
    assert result is None


def test_try_answer_tabular_question_greater_than_numeric(mocker):
    rows = parse_table(
        "Name | Score\nAlice | 90\nBob | 40\nCarol | 75"
    )
    spec = TabularQuerySpec(
        applicable=True,
        filters=[ColumnFilter(column="Score", op="greater_than", value="50")],
        action="list",
    )
    mocker.patch("app.agents.tabular.get_llm").return_value.call.return_value = spec

    handled, result = try_answer_tabular_question(rows, "who scored above 50")

    assert handled is True
    assert "Alice" in result
    assert "Carol" in result
    assert "Bob" not in result
