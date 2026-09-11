---
name: run-research-summarize
description: Build, run, and drive the Research & Summarize app (FastAPI + CrewAI backend, Celery worker, React frontend, Docker Compose). Use when asked to start/run/build the app, run its tests, screenshot its UI, submit a job through the API, or verify a change actually works end-to-end.
---

This is a Docker Compose app (Postgres + Valkey + FastAPI backend + Celery
worker + nginx-served React frontend). Drive the API with `curl`; drive the
UI with the Playwright-based REPL at
`.claude/skills/run-research-summarize/driver.mjs` (this environment has no
`chromium-cli`, so this fallback driver exists and uses the same command
vocabulary). All paths below are relative to the repo root.

## Prerequisites

- Docker Desktop, daemon running (`docker info` succeeds).
- Node 18+ with `npx` (for the Playwright driver, if driving the UI).
- No local Python/Postgres/Redis needed for the Docker path -- everything
  runs in containers.

## Setup

```powershell
cd C:\Users\prasa\Automation\Agents\Research_Summarize
Copy-Item .env.example .env
# Edit .env: set OPENAI_API_KEY and SERPER_API_KEY for a real run.
# For a smoke test only (proving the app runs, not a real summary), any
# placeholder value works -- see Gotchas: this now fails a bad key cleanly
# within ~12 minutes instead of hanging (see the crewai hang below).
```

This machine may already have unrelated Docker projects using the default
ports. Check first and override via `.env` (`BACKEND_PORT`,
`FRONTEND_PORT`) if needed:
```powershell
Get-NetTCPConnection -LocalPort 8000,8080 -ErrorAction SilentlyContinue
```
(This session used `BACKEND_PORT=8010` because 8000 was already taken by
an unrelated project.)

## Build

```powershell
docker compose build
```
Slow (5-10+ min) on a cold cache -- crewai's dependency tree (chromadb,
onnxruntime, litellm, opentelemetry...) is large. Fast on a warm cache
(seconds). **Keep config-only `ENV` edits in `backend/Dockerfile` after the
`pip install` layer**, not before it, or you'll force a full reinstall on
every tweak (hit this once, see NOTES.md).

## Run (agent path)

```powershell
docker compose up -d
docker compose ps        # all 5 services should show Up (postgres/valkey "healthy")
curl.exe -s http://localhost:8010/health   # {"status":"ok"}  (use your BACKEND_PORT)
```

**Drive the API directly** (fastest way to verify backend + worker + DB +
queue wiring):
```powershell
# Submit a job (either -F url=<link>, or -F file=@path for an upload)
curl.exe -s -X POST "http://localhost:8010/api/jobs" -F "url=https://en.wikipedia.org/wiki/Solar_System"
# -> {"job_id":"...","status":"pending","content_type":"website"}

curl.exe -s "http://localhost:8010/api/jobs/<job_id>"   # poll until status is completed/failed
```
A dead/unreachable URL fails cleanly in ~2s with a friendly message --
good smoke test that needs no LLM key at all:
```powershell
curl.exe -s -X POST "http://localhost:8010/api/jobs" -F "url=https://this-domain-does-not-exist-12345.invalid/x"
```

**Drive the UI** with the Playwright REPL driver (same command vocabulary
as `chromium-cli`: `nav` / `wait-for` / `click` / `fill` / `press` /
`screenshot` / `console --errors` / `quit`, plus one addition,
`mock-get <url-glob> <json-file>`, documented below):
```powershell
cd .claude\skills\run-research-summarize
npm install              # first time only
npx playwright install chromium   # first time only

@'
nav http://localhost:8080
wait-for text=Research & Summarize
screenshot home
fill input[type=text] https://en.wikipedia.org/wiki/Large_language_model
click text=Summarize link
wait-for text=Extracting
screenshot processing
console --errors
quit
'@ | node driver.mjs --session app
```
Screenshots land in `sessions/<session>/screenshots/`. **Use plain
selectors with no embedded spaces** (`input[type=text]`, not
`input[aria-label="URL to summarize"]`) -- the line-based parser here
splits on spaces and doesn't handle quoted values (see Gotchas).

**Proving the completed/failed views without a real OpenAI key**: this
session had no paid API key available, so instead of waiting on a real
LLM call, `mock-get` intercepts the frontend's `GET /api/jobs/*` polling
requests client-side and fulfills them with a canned JSON body -- the real
job still gets created and processed server-side (harmless), but the
*browser* sees whatever you hand it, proving the rendering path
faithfully. Two ready-made fixtures are in `fixtures/`:
```powershell
@'
nav http://localhost:8080
wait-for text=Research & Summarize
fill input[type=text] https://en.wikipedia.org/wiki/Large_language_model
click text=Summarize link
wait-for text=Extracting
mock-get **/api/jobs/* .claude\skills\run-research-summarize\fixtures\mock_completed_job.json
wait-for text=A practical primer
screenshot results
quit
'@ | node driver.mjs --session app
```
Swap in `fixtures/mock_failed_job.json` and `wait-for text=couldn't finish`
to see the failed-state view instead.

## Run (human path)

`docker compose up -d`, then open `http://localhost:8080` (or your
`FRONTEND_PORT`) in a real browser. `docker compose down` to stop (add
`-v` to also wipe the Postgres/Valkey volumes).

## Test

```powershell
cd backend
py -3.11 -m venv .venv        # crewai has no wheels for very new Python
                               # yet -- if your default `python` is too
                               # new, an older interpreter (3.11 here) is
                               # needed. `py -0p` lists what's installed.
.venv\Scripts\pip.exe install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -v
```
Expected: **33 passed**. No Docker/Postgres/Redis/OpenAI needed -- tests
use a throwaway local SQLite file and mock every external call.

---

## Gotchas

- **A real crewai 1.15.21 bug: worker can spin forever on LLM failure.**
  A bad/invalid `OPENAI_API_KEY` doesn't just fail the job -- part of
  crewai's first-run tracing-consent flow can stall for minutes acquiring
  a file lock (root-caused and partially fixed: `backend/Dockerfile`
  pre-seeds crewai's own state file at build time so that specific stall
  is closed). A **second, separate** stall past that point is not fully
  root-caused. Mitigation: `task_soft_time_limit=720` /
  `task_time_limit=780` in `backend/app/core/celery_app.py` guarantee any
  job that hits this fails cleanly within ~12-13 min instead of hanging
  forever. **Only triggers on a broken API key** -- a real key never
  reaches this path. Full forensic diagnosis (source files, line numbers,
  timings) in `NOTES.md` in this directory -- read it before spending more
  time on this if it resurfaces.
- **nginx `proxy_pass` with a variable silently drops part of the URI.**
  `frontend/nginx.frontend.conf` uses `set $backend_upstream backend:8000;`
  so nginx re-resolves the "backend" container name past its default
  DNS-caching (needed for surviving `docker compose up --force-recreate
  backend`). But `proxy_pass http://$backend_upstream/api/;` (URI
  included) does NOT do the usual location-prefix rewrite that a literal
  proxy_pass target gets -- `POST /api/jobs` arrived at the backend as
  `POST /api/` (silently missing `jobs`). Fix: no URI after the variable
  (`proxy_pass http://$backend_upstream;`), forwarding the original
  request path unchanged.
- **The line-based driver parser splits on spaces.** A selector containing
  a quoted attribute with spaces (`input[aria-label="URL to summarize"]`)
  breaks it. Use selectors with no embedded spaces.
- **SQLAlchemy's `Enum(..., native_enum=False)` stores the Python enum
  *name*, not its `.value`.** Hand-seeding a row via raw SQL with
  `status='completed'` (matching `JobStatus.COMPLETED`'s value) 500s on
  read -- it has to be `status='COMPLETED'` (the member name). Only
  matters if you bypass the ORM (e.g. seeding demo data directly in psql,
  as this session did) -- real app code via `Job(status=JobStatus.X, ...)`
  is unaffected.

## Troubleshooting

- **`docker compose up` fails with "port is already allocated"**: another
  project's containers are already using that host port (check
  `docker ps -a` -- this machine had an unrelated `video_content-*` stack
  running). Don't stop someone else's containers; set `BACKEND_PORT` /
  `FRONTEND_PORT` in `.env` to free ports instead.
- **`ResponseValidationError` / 500 on `GET /api/jobs/{id}`**: was a real
  bug (now fixed) -- the route returned the raw SQLAlchemy `Job` ORM
  object, whose primary key is `.id`, against a `JobStatusResponse` schema
  expecting `.job_id`. If you see this again after editing
  `backend/app/api/routes/jobs.py`, you likely reverted the explicit
  `JobStatusResponse(...)` construction back to `return job`.
  `pytest`/`GET`ing the endpoint immediately surfaces it -- adding an API
  field is not safe to skip testing.
- **`docker compose build` suddenly takes 5-10 minutes again** after a
  one-line Dockerfile edit: an `ENV` line was added before
  `COPY requirements.txt` / `pip install`, invalidating every layer after
  it. Move config-only `ENV` lines to after the pip-install layer.
- **502 from nginx right after `docker compose up -d --force-recreate
  backend`** (but not on a full `docker compose up`): nginx cached the old
  backend container's IP. Already fixed via the `resolver` + variable
  pattern in `nginx.frontend.conf` (see Gotchas) -- if it recurs, check
  that fix wasn't reverted.
- **`pip install crewai` fails with no matching version**: your default
  Python is too new for crewai's current wheels. Use an older interpreter
  (`py -0p` to list what's installed on Windows; this session used 3.11).
