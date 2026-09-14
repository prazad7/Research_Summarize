from app.db.base import SessionLocal
from app.db.models import Job, JobStatus

_SAMPLE_RESULT = {
    "headline": "A quarterly budget summary.",
    "key_takeaways": ["Rent is the largest expense.", "Spending is within budget."],
    "entities": ["Rent"],
    "sources": [],
    "verification_notes": None,
    "content_title": "budget",
    "raw_transcript": None,
}


def _complete_job(job_id: str, extracted_text: str = "Some extracted source text.") -> None:
    """The Celery task doesn't run for real in these tests (see conftest),
    so completion is applied directly -- mirrors what `tasks/pipeline.py`
    would have written on success."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = JobStatus.COMPLETED
        job.result = _SAMPLE_RESULT
        job.extracted_text = extracted_text
        db.commit()
    finally:
        db.close()


def _create_completed_job(client, mocker) -> str:
    mocker.patch("app.api.routes.jobs.process_content_job.delay")
    response = client.post("/api/jobs", data={"url": "https://example.com/budget"})
    job_id = response.json()["job_id"]
    _complete_job(job_id)
    return job_id


def test_send_message_requires_completed_job(client, mocker):
    mocker.patch("app.api.routes.jobs.process_content_job.delay")
    response = client.post("/api/jobs", data={"url": "https://example.com/pending"})
    job_id = response.json()["job_id"]

    chat_response = client.post(
        f"/api/jobs/{job_id}/messages", json={"message": "What is this about?"}
    )
    assert chat_response.status_code == 409


def test_send_message_404_for_unknown_job(client):
    response = client.post("/api/jobs/does-not-exist/messages", json={"message": "Hi"})
    assert response.status_code == 404


def test_send_message_returns_grounded_reply(client, mocker):
    job_id = _create_completed_job(client, mocker)
    mocker.patch(
        "app.api.routes.chat.build_chat_reply",
        return_value="Rent is the largest line item in this budget.",
    )

    response = client.post(
        f"/api/jobs/{job_id}/messages", json={"message": "What's the biggest expense?"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert "Rent" in body["content"]


def test_list_messages_returns_history_in_order(client, mocker):
    job_id = _create_completed_job(client, mocker)
    mocker.patch("app.api.routes.chat.build_chat_reply", return_value="First reply.")
    client.post(f"/api/jobs/{job_id}/messages", json={"message": "First question?"})

    history_response = client.get(f"/api/jobs/{job_id}/messages")

    assert history_response.status_code == 200
    roles = [m["role"] for m in history_response.json()]
    assert roles == ["user", "assistant"]


def test_send_message_keeps_user_message_when_llm_call_fails(client, mocker):
    """The user's own message is persisted before the LLM call runs, so a
    failed/unavailable LLM doesn't force them to retype their question."""
    job_id = _create_completed_job(client, mocker)
    mocker.patch("app.api.routes.chat.build_chat_reply", side_effect=RuntimeError("LLM down"))

    response = client.post(f"/api/jobs/{job_id}/messages", json={"message": "Will this fail?"})
    assert response.status_code == 502

    history_response = client.get(f"/api/jobs/{job_id}/messages")
    roles = [m["role"] for m in history_response.json()]
    assert roles == ["user"]
