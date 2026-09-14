"""Follow-up chat over a completed job's content.

Deliberately NOT a CrewAI agent/task/crew -- "answer a question grounded in
text I already have" needs one LLM call, not a multi-agent pipeline with a
web-search tool. Reuses `get_llm()` so a provider/model swap stays in the
one place (`agents/llm.py`) that already handles it for the summarization
crew; this module only owns the chat-specific system prompt.
"""
from __future__ import annotations

from app.agents.llm import get_llm
from app.agents.tabular import parse_table, try_answer_tabular_question

# Content types whose extracted_text is the flattened '## Sheet: X' / header /
# ' | '-joined-rows format produced by excel_extractor.py and csv_extractor.py --
# the only ones the deterministic filter/count/list path in tabular.py applies to.
_TABULAR_CONTENT_TYPES = {"xlsx", "csv"}

_SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant answering follow-up questions about ONE specific piece of content a user already uploaded or linked, titled "{title}" ({content_type}).

Below is the extracted source content, followed by the summary already generated from it. Answer the user's questions using ONLY this material -- do not use outside knowledge, do not browse the web, and do not speculate beyond what's here.

If the user's question is unrelated to this content -- general knowledge questions, requests about something else entirely, or anything this material simply doesn't cover -- politely decline. Say plainly that you can only help with questions about this uploaded content, and briefly remind them what it's about instead of attempting an answer. Never answer an unrelated question from outside knowledge just to be helpful.

If the source content below is tabular (a header row of column names, followed by one record per line with values in that same column order, separated by " | "), read it precisely rather than approximately:
- Match column names to values strictly by position against the header row on that same line -- never guess or borrow a value from a neighboring column, and never blend in a value from a different row.
- For a question about one specific column or row, report exactly and only that field's value(s) for the exact matching row(s) -- do not incorporate other columns unless asked.
- For a question involving a condition on more than one column at once (e.g. "how many from X enrolled in Y", "list students from X who paid the fee"), check every relevant column independently for each row and count/list only the rows where every condition holds -- do not approximate or estimate.
- Column values may appear in different letter casing across rows (e.g. "Chennai", "CHENNAI", "chennai") -- treat these as the same value when matching, unless the user's question is specifically about casing.
- When asked "how many" or to filter/list rows matching a condition, do NOT estimate a count from memory or general impression. Silently work through the rows in order first and build a private list of every matching row's ID/name (do not show this row-by-row scratch work in your reply); the count is the length of that list, and if the user asked for a list, that list -- checked once more before answering -- is the answer. Then reply with ONLY the final, concise result: just the number for a count, or a clean list for a list request.

--- SOURCE CONTENT START ---
{content}
--- SOURCE CONTENT END ---

--- SUMMARY ---
{summary}
--- END SUMMARY ---

Keep answers concise and plain-language, matching the tone of the summary above. It's fine to quote or reference specific figures, rows, or passages from the source content when relevant."""


def build_chat_reply(
    *,
    title: str,
    content_type: str,
    extracted_text: str,
    summary_text: str,
    history: list[dict[str, str]],
    user_message: str,
) -> str:
    """Returns the assistant's reply text for one chat turn.

    `history` is prior turns as [{"role": "user"|"assistant", "content": ...}, ...],
    oldest first, NOT including `user_message` itself -- the caller is
    responsible for bounding how far back this goes.

    For Excel/CSV content, a "how many .../list ... where ..." style
    question is answered deterministically first (see tabular.py) rather
    than left to the LLM to count by reading -- that's unreliable even on
    a modest-sized table. Everything else (open-ended questions, and every
    non-tabular content type) uses the single grounded LLM call below,
    unchanged.
    """
    if content_type in _TABULAR_CONTENT_TYPES:
        rows = parse_table(extracted_text)
        handled, computed_result = try_answer_tabular_question(rows, user_message)
        if handled:
            return _phrase_computed_result(
                title=title,
                content_type=content_type,
                computed_result=computed_result or "",
                history=history,
                user_message=user_message,
            )

    return _free_text_reply(
        title=title,
        content_type=content_type,
        extracted_text=extracted_text,
        summary_text=summary_text,
        history=history,
        user_message=user_message,
    )


def _free_text_reply(
    *,
    title: str,
    content_type: str,
    extracted_text: str,
    summary_text: str,
    history: list[dict[str, str]],
    user_message: str,
) -> str:
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        title=title,
        content_type=content_type,
        content=extracted_text,
        summary=summary_text,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Lower than the summarization crew's default (0.3, unchanged there) --
    # answers here should be as consistent and literal as possible, not
    # creatively varied, so chat gets its own low temperature rather than
    # sharing the crew's setting.
    llm = get_llm(temperature=0.0)
    reply = llm.call(messages)
    return reply.strip() if isinstance(reply, str) else str(reply)


def _phrase_computed_result(
    *,
    title: str,
    content_type: str,
    computed_result: str,
    history: list[dict[str, str]],
    user_message: str,
) -> str:
    """Turns an already-exact, already-computed result into a natural-
    language reply -- the LLM's only job here is phrasing, never
    recomputing or second-guessing the number/list it's given."""
    system_prompt = (
        f'You are answering a question about a table titled "{title}" ({content_type}). '
        "The exact answer below was already computed programmatically by scanning every "
        "row -- treat it as ground truth and present it as your answer; do not recompute, "
        "second-guess, or adjust it, and do not add rows or figures that aren't in it.\n\n"
        f"{computed_result}\n\n"
        "Reply concisely in plain language. If it's a count, just state the number "
        "plainly. If it's a list, present the matching rows clearly (e.g. a short "
        "bulleted list of the identifying details), and mention the total count too."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    llm = get_llm(temperature=0.0)
    reply = llm.call(messages)
    return reply.strip() if isinstance(reply, str) else str(reply)
