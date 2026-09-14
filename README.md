# Research & Summarize

Paste a link or drop a file — a website, YouTube video, PDF, Word, Excel,
CSV, PowerPoint, audio recording, or video recording — and get back a clean,
research-backed summary: a headline, 4-6 key takeaways, notable
entities/topics, and the sources used to verify or add context, with a
plain-language note if something couldn't be verified. Once the summary is
ready, you can keep chatting: ask follow-up questions and get answers
grounded in the content you uploaded — anything unrelated gets a polite
decline instead of a made-up answer.

Behind the scenes, a three-agent [CrewAI](https://github.com/crewAIInc/crewAI)
pipeline (Content Analyst → Research Verifier → Summary Writer) produces the
summary; the end user never sees any of that, just: drop something in, wait
briefly, read the result, then ask it anything.

## How it works

```
React frontend                 FastAPI backend                  Celery worker
─────────────────              ─────────────────                ───────────────────────
Paste URL / drop  ── POST ──▶  Validate + detect     ── enqueue ▶  Extract content
file                           content type,                        (per-type extractor)
                                save Job (pending)                        │
                                                                          ▼
Poll job status   ── GET  ──▶  Read Job row from     ◀── update ── CrewAI crew:
every ~2.5s                    Postgres                             Content Analyst
                                                                      → Research Verifier
Render result                                                          (SerperDev search)
(never raw JSON)                                                      → Summary Writer
                                                                          │
                                                                          ▼
                                                                   Save result (completed)
                                                                   or friendly error (failed)

Once completed         ── POST ──▶  Answer from the job's
Ask a follow-up          /messages    saved extracted_text +
question                             summary only (no web
                        ◀── reply ──  search) -- politely
                                      declines anything else
```

- The frontend never talks to Celery/CrewAI directly — only to the FastAPI
  REST API, which is documented automatically at `/docs` (OpenAPI/Swagger).
- Long-running work (transcription, long documents, research) runs in a
  background Celery worker so the API responds instantly with a `job_id`;
  the frontend polls `GET /api/jobs/{job_id}` until the job is
  `completed` or `failed`.
- Adding a new input type = one new class in `backend/app/ingestion/` +
  one line in `backend/app/ingestion/base.py`'s registry. Nothing else
  changes (CSV support was added exactly this way).
- Swapping the LLM/provider = one function in `backend/app/agents/llm.py`.
- Once a job is `completed`, `POST /api/jobs/{job_id}/messages` answers
  follow-up questions about that specific job — synchronously (no job
  queue/polling involved, since a single grounded LLM call is fast enough
  to answer within the request). It's a single LLM call grounded in that
  job's saved `extracted_text` and summary only, with no web-search tool,
  and is instructed to decline anything unrelated to the uploaded content
  rather than answer from general knowledge. History is persisted per job
  in a `chat_messages` table (`GET` the same path to replay it).

## Tech stack

| Layer            | Choice                                                        |
|-------------------|----------------------------------------------------------------|
| Agent pipeline    | CrewAI (3 agents, sequential process), OpenAI `gpt-4o-mini`   |
| Research tool     | SerperDevTool (Serper.dev search API) via `crewai-tools`      |
| Backend API       | FastAPI + Pydantic, typed request/response models              |
| Background jobs   | Celery + Valkey (open-source, Redis-protocol-compatible)       |
| Persistence       | PostgreSQL (job status/results)                                |
| Frontend          | React + TypeScript + Vite, no UI framework dependency          |
| Deployment        | Docker Compose (same file for localhost today, your VPS later) |

This project is sized for **light, single-user traffic** (a personal
project / portfolio deployment), not high concurrency — see
[Scaling notes](#scaling-notes) if that ever needs to change.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recommended path), **or** Python 3.11+, Node 20+, PostgreSQL 16, Redis/Valkey, and `ffmpeg` + `tesseract-ocr` installed locally for the manual path.
- An [OpenAI API key](https://platform.openai.com/api-keys) with access to `gpt-4o-mini`.
- A [Serper.dev](https://serper.dev) API key (free tier available) for the research/verification step.

## Quickstart (Docker Compose — recommended)

```bash
git clone <this-repo>
cd Research_Summarize
cp .env.example .env
# edit .env: set OPENAI_API_KEY and SERPER_API_KEY at minimum

docker compose up --build
```

Then open:
- **App:** http://localhost:8080
- **API docs:** http://localhost:8000/docs

That's it — Postgres, Valkey, the FastAPI backend, the Celery worker, and
the built React app all start together. Uploaded files and the database
persist in Docker volumes across restarts (`docker compose down` keeps
them; add `-v` to wipe them).

## Running without Docker (manual)

Useful for active backend development with hot reload.

**1. Start Postgres + Valkey** (easiest via Docker even if the rest runs natively):
```bash
docker compose up -d postgres valkey
```

**2. Backend API:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env          # edit with your API keys
uvicorn app.main:app --reload --port 8000
```

**3. Celery worker** (separate terminal, same venv):
```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info --concurrency=2 -P solo
```
(`-P solo` avoids Windows multiprocessing issues with Celery's default pool; drop it on Linux/macOS.)

**4. Frontend:**
```bash
cd frontend
npm install
cp .env.example .env          # default already points at localhost:8000
npm run dev
```

Open http://localhost:5173.

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults. The
ones you must set yourself:

| Variable          | Required | Purpose                                              |
|--------------------|----------|-------------------------------------------------------|
| `OPENAI_API_KEY`   | Yes      | Powers all three CrewAI agents (`gpt-4o-mini`)        |
| `SERPER_API_KEY`   | Yes      | Web search for the Research Verifier agent            |
| `APP_API_KEY`      | Recommended once public | Shared key the frontend sends as `X-API-Key`. Blank = no auth (fine for pure localhost only). |

Everything else (file size limits, media duration limits, OCR fallback,
truncation length, ports, log level) has a sensible default and can be
tuned per-environment without touching code.

## Running tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Tests run against a throwaway local SQLite file (no Postgres/Redis/OpenAI
required) and cover: content-type detection, upload validation, the
error-message mapping shown to users, the PDF/DOCX/Excel/CSV extractors
(including corrupt-file and no-extractable-text paths), the job API's
request validation and status flow, and the chat API (grounded replies,
gating on job completion, and history surviving a failed LLM call).
External calls (OpenAI, Serper, network fetches, the actual Celery task)
are mocked at the boundary rather than exercised for real, since those
depend on paid third-party APIs.

## Project structure

```
backend/
  app/
    main.py              FastAPI app, CORS, startup
    config.py             All settings, env-var driven
    security.py            API key dependency
    db/                    SQLAlchemy models (Job, ChatMessage) + session
    schemas/                Pydantic request/response models (job.py, chat.py)
    api/routes/              /api/jobs, /api/jobs/{id}/messages (chat), /health
    ingestion/                One extractor per input type + the registry
      base.py                  BaseExtractor interface + get_extractor()
      detect.py                 URL/filename -> ContentType
      url_extractor.py, youtube_extractor.py, pdf_extractor.py,
      docx_extractor.py, excel_extractor.py (.xlsx + legacy .xls),
      csv_extractor.py, pptx_extractor.py,
      audio_extractor.py, video_extractor.py, audio_utils.py (shared Whisper helper)
      exceptions.py             User-facing error types
    agents/                  CrewAI pipeline + chat
      llm.py                    LLM construction (the one place to swap models/providers)
      tools.py                   SerperDevTool wiring
      agents_def.py, tasks_def.py, crew.py
      schemas.py                 Structured outputs (ContentAnalysis, ResearchFindings, SummaryResult)
      chat.py                    Follow-up chat: one grounded LLM call, no crew/tools
      tabular.py                 Deterministic filter/count/list for Excel/CSV chat questions
    core/celery_app.py        Celery app config
    tasks/pipeline.py          The end-to-end Celery task (persists extracted_text for chat)
    storage/file_storage.py    Upload persistence
  tests/                     pytest suite
frontend/
  src/
    App.tsx                   Top-level state machine (input -> processing -> results)
    api/client.ts               Typed fetch wrapper
    components/                 InputPanel, ProgressView, ResultsView, ChatPanel, ApiKeyGate
    types.ts                    Shared TypeScript types (mirrors the backend Pydantic schemas)
docker-compose.yml           postgres, valkey, backend, worker, frontend
```

## Design notes & tradeoffs

- **No Alembic migrations.** `init_db()` runs `create_all()` on startup,
  which creates missing tables (like `chat_messages`) but never alters an
  existing one's columns. A fresh deployment picks up the full current
  schema automatically; an existing local/dev database needs a reset
  (`docker compose down -v`) to pick up a new column on `jobs` (e.g.
  `extracted_text`). If the schema keeps growing, introducing Alembic is a
  clean, isolated addition — it wasn't worth the operational overhead for
  a first deployment.
- **Valkey, not Redis.** Redis's license changed in 2024 for new
  versions; Valkey is the Linux Foundation's open-source, drop-in
  compatible fork (same protocol, same client libraries), so the stack
  stays fully open source with zero code differences.
- **Extraction is deterministic Python, not an LLM agent.** Parsing a
  PDF/DOCX/XLSX/PPTX, fetching a webpage, or transcribing audio doesn't
  need an LLM — only the analysis/research/writing steps do. This keeps
  extraction fast, cheap, and easy to unit test without mocking an LLM.
- **Content is truncated** (`TRUNCATE_CONTENT_CHARS`, default ~14k
  characters) before reaching the crew, to keep LLM cost/latency bounded
  for very long transcripts or documents. The summary notes when this
  happened.
- **Errors are mapped, not leaked.** Every extraction failure is a typed
  `IngestionError` with a plain-language `user_message`; anything
  unexpected falls back to a generic message. Full technical detail
  (stack trace, exception type) goes to structured logs only, tagged with
  the `job_id`, never to the API response. (`excel_extractor.py` catching
  `zipfile.BadZipFile` explicitly, not just `OSError`, is exactly this
  pattern earning its keep — a legacy `.xls` upload isn't a zip container
  at all, and `BadZipFile` doesn't subclass `OSError`, so without this it
  escaped as an unmapped exception and surfaced the generic message
  instead of a clear "damaged or unexpected format" one.)
- **Chat is grounded and scoped on purpose.** Follow-up questions
  (`agents/chat.py`) are answered from that job's saved `extracted_text` +
  summary only, via a single direct LLM call with no web-search tool —
  unlike the summarization crew, it must never answer from outside
  knowledge. The system prompt instructs it to politely decline anything
  the uploaded content doesn't cover, rather than answer it anyway.
- **Excel/CSV blank cells keep their column position.** Both extractors
  used to drop a blank cell instead of keeping it as an empty field, which
  silently shifted every later value in that row one column to the left —
  e.g. a row with a blank `Phone` would end up with its `City` value
  sitting under the `Fee_Paid` column instead. Harmless for a human
  skimming the summary, but it broke any chat question that depended on
  reading a specific column correctly. Fixed by always keeping blank
  cells as empty fields and only skipping a row that's entirely blank.
- **Exact counting/filtering on tabular chat questions is computed, not
  asked of the LLM.** A single LLM call reading a table and being asked
  "how many..." is unreliable even at a few dozen rows — confirmed
  directly: it stayed wrong across multiple prompt-engineering attempts
  (enumerate-before-answering, temperature 0) on a real 50-row file. For
  Excel/CSV, `agents/tabular.py` instead asks the LLM only to translate
  the question into a small structured filter (real column name + op +
  value, using the same structured-output mechanism the summarization
  crew already relies on via `output_pydantic`), executes that filter in
  plain Python against the already-extracted rows, and asks the LLM only
  to phrase the exact, precomputed result — never to recompute it. This
  is intentionally scoped to the same bounded `extracted_text` every
  other content type already uses (same row/char caps, no new
  dependency, no re-reading the original file for very large uploads —
  that's a deliberately separate concern for later).

## Scaling notes

Current defaults (Celery concurrency, Postgres/Valkey with no tuning,
single backend replica) target light, single-user traffic. If usage ever
grows: raise `--concurrency` on the `worker` service, run multiple
`worker` replicas, and move Postgres/Valkey to managed services — none of
that requires restructuring the app itself, since the job queue already
decouples request handling from processing.

## Deploying to your VPS later

1. Copy the repo to the VPS, create a real `.env` (a strong `APP_API_KEY`,
   your real API keys, and `CORS_ORIGINS`/frontend URL if it differs).
2. `docker compose up -d --build`.
3. Put a reverse proxy with TLS in front of the `frontend` service's port
   (e.g. [Caddy](https://caddyserver.com/) for automatic HTTPS, or nginx +
   certbot) — the app itself doesn't terminate TLS.
4. Point your domain's DNS at the VPS and you're live. No code changes
   needed versus the localhost setup.
