from app.agents.chat import build_chat_reply


def test_build_chat_reply_uses_deterministic_result_for_tabular_content(mocker):
    mocker.patch("app.agents.chat.parse_table", return_value=[{"City": "Chennai"}])
    mocker.patch(
        "app.agents.chat.try_answer_tabular_question",
        return_value=(True, "The exact count, computed from every matching row, is 16."),
    )
    fake_llm = mocker.patch("app.agents.chat.get_llm").return_value
    fake_llm.call.return_value = "There are 16 students from Chennai."

    reply = build_chat_reply(
        title="Book1",
        content_type="xlsx",
        extracted_text="Name | City\nAlice | Chennai",
        summary_text="A student list.",
        history=[],
        user_message="how many students are from chennai",
    )

    assert reply == "There are 16 students from Chennai."
    # The phrasing call must be told the exact computed result verbatim.
    system_message = fake_llm.call.call_args[0][0][0]["content"]
    assert "16" in system_message


def test_build_chat_reply_falls_back_to_free_text_when_not_a_filter_question(mocker):
    mocker.patch("app.agents.chat.parse_table", return_value=[{"City": "Chennai"}])
    mocker.patch("app.agents.chat.try_answer_tabular_question", return_value=(False, None))
    fake_llm = mocker.patch("app.agents.chat.get_llm").return_value
    fake_llm.call.return_value = "This table is about student enrollments."

    reply = build_chat_reply(
        title="Book1",
        content_type="xlsx",
        extracted_text="Name | City\nAlice | Chennai",
        summary_text="A student list.",
        history=[],
        user_message="what is this data about",
    )

    assert reply == "This table is about student enrollments."


def test_build_chat_reply_skips_tabular_path_for_non_tabular_content(mocker):
    tabular_check = mocker.patch("app.agents.chat.try_answer_tabular_question")
    fake_llm = mocker.patch("app.agents.chat.get_llm").return_value
    fake_llm.call.return_value = "This article covers three main points."

    reply = build_chat_reply(
        title="An article",
        content_type="website",
        extracted_text="Some article text.",
        summary_text="A short article summary.",
        history=[],
        user_message="what does this article cover",
    )

    assert reply == "This article covers three main points."
    tabular_check.assert_not_called()
