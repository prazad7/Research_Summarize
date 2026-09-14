def test_create_job_requires_exactly_one_of_url_or_file(client):
    response = client.post("/api/jobs", data={})
    assert response.status_code == 400


def test_create_job_with_url_enqueues_and_returns_job_id(client, mocker):
    mocker.patch("app.api.routes.jobs.process_content_job.delay")

    response = client.post("/api/jobs", data={"url": "https://example.com/some-article"})

    assert response.status_code == 201
    body = response.json()
    assert body["content_type"] == "website"
    assert body["status"] == "pending"
    assert body["job_id"]


def test_create_job_with_youtube_url(client, mocker):
    mocker.patch("app.api.routes.jobs.process_content_job.delay")

    response = client.post(
        "/api/jobs", data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )

    assert response.status_code == 201
    assert response.json()["content_type"] == "youtube"


def test_create_job_rejects_invalid_url(client):
    response = client.post("/api/jobs", data={"url": "not-a-url"})
    assert response.status_code == 422


def test_create_job_rejects_unsupported_file_extension(client):
    response = client.post(
        "/api/jobs", files={"file": ("archive.zip", b"fake-bytes", "application/zip")}
    )
    assert response.status_code == 422


def test_create_job_accepts_csv_upload(client, mocker):
    mocker.patch("app.api.routes.jobs.process_content_job.delay")

    response = client.post(
        "/api/jobs", files={"file": ("data.csv", b"Name,Age\nAlice,30\n", "text/csv")}
    )

    assert response.status_code == 201
    assert response.json()["content_type"] == "csv"


def test_get_job_status_not_found(client):
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404


def test_get_job_status_after_creation(client, mocker):
    mocker.patch("app.api.routes.jobs.process_content_job.delay")

    create_response = client.post("/api/jobs", data={"url": "https://example.com/article"})
    job_id = create_response.json()["job_id"]

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"
    assert body["result"] is None
