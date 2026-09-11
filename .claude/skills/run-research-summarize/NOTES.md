# Forensic notes from building this run skill

Kept as a reference alongside SKILL.md -- SKILL.md's Gotchas section
summarizes these; this file has the full detail (source paths, line
numbers, timings) for anyone who needs to pick the open crewai issue back
up.

## Environment
- NOT a Linux container -- Windows 11 host, PowerShell as the working shell.
  Bash tool here is missing most coreutils (no `sh`, `ls`, `grep`, `mkdir`,
  `cat`...) so everything below was run via the PowerShell tool instead.
- Docker Desktop IS installed and the daemon is running (`docker info`
  succeeds, backend: docker-desktop, WSL2).
- `chromium-cli` is NOT available anywhere on this machine (checked PATH,
  npm global, `.claude/`). Built a Playwright-based fallback driver
  (`driver.mjs`) with the same command vocabulary, per the skill-generator's
  own fallback guidance.

## Local (non-Docker) backend verification
- System `python` resolved to 3.14.7 -- crewai has no wheels for 3.14 yet
  (`ERROR: Could not find a version that satisfies the requirement
  crewai>=0.83.0`, only pre-1.0 versions listed as compatible candidates
  for other constraints). Used `py -3.11` (present on this machine) to
  create the venv instead. Worth remembering: crewai support lags new
  CPython releases by a while.
- Installed crewai resolved to **1.15.21** (requirements.txt pins
  `crewai>=0.83.0`, unbounded) -- huge version gap from what was assumed
  while writing the code, but verified compatible: Agent/Task/Crew/LLM
  field names (`role`, `goal`, `backstory`, `llm`, `output_pydantic`,
  `context`, `callback`, `CrewOutput.pydantic`, `crewai.TaskOutput`
  top-level export) all still match 1.15.x exactly. No code changes needed.
- `pytest` run against the real installed deps caught two real bugs that
  static review + compiling had missed:
  1. `GET /api/jobs/{id}` returned the raw SQLAlchemy `Job` ORM object as
     the response body; FastAPI's `response_model=JobStatusResponse`
     validation failed because the ORM's primary key is `Job.id` but the
     API field is `job_id` -- every status poll would have 500'd. Fixed by
     building the `JobStatusResponse` explicitly in the route instead of
     relying on `from_attributes` field-name coincidence.
  2. Test teardown deleted the SQLite test DB file while the SQLAlchemy
     engine still held a handle open -- `PermissionError` on Windows only
     (POSIX allows deleting open files; Windows doesn't). Fixed with
     `engine.dispose()` before `os.remove()`, wrapped in try/except as a
     last-resort.
- All 33 tests pass after both fixes.

## Docker build
- `docker compose build` for the backend image (crewai's dependency tree:
  chromadb, onnxruntime, litellm, opentelemetry, tokenizers, ...) took a
  long time from cold cache -- budget for it, don't assume a hang.
- Editing an `ENV` line placed BEFORE `COPY requirements.txt` / `pip install`
  invalidates every layer after it, forcing a full dependency reinstall on
  the next build. Keep config-only `ENV` tweaks *after* the pip-install
  layer so iterating on them stays fast.

## Port conflicts
- This machine already had an unrelated project's docker-compose stack
  running (a completely different app, `video_content-*` containers, up
  for 12 days) occupying host ports 8000, 5432, 6379, 5173, 80. Don't stop
  or touch another project's containers -- just publish this stack on free
  ports instead (`BACKEND_PORT=8010` here; check with
  `Get-NetTCPConnection -LocalPort <port>` before assuming a port is free).

## A real crewai 1.15.21 bug: the worker can hang indefinitely on LLM failure
Submitted a real job (a live Wikipedia URL, deliberately invalid
`OPENAI_API_KEY`) through the full docker-compose stack. Extraction
succeeded, the crew kicked off, and the LLM call correctly reached
`https://api.openai.com` and got a real 401 -- then the worker sat at
"analyzing" indefinitely: 99% CPU, growing memory, but **zero** new network
I/O (checked with `docker stats` twice a few seconds apart). Not a hang on
a network call -- a local CPU-bound spin.

Root-caused by reading the installed `crewai`/`crewai_core` source directly
(not from any changelog -- this version is far newer than anything in
training data): on a Crew/Task failure, `FirstTimeTraceHandler` in
`crewai/events/listeners/tracing/first_time_trace_handler.py` runs a
one-time "first execution" flow that (a) tries an interactive
"view your execution traces? [y/N]" prompt -- correctly skipped here since
stdin isn't a tty -- and then (b) unconditionally calls
`mark_first_execution_done()`, which acquires a `portalocker`-based file
lock (`crewai_core/lock_store.py`, 120s default timeout) around
`~/.local/share/<CREWAI_STORAGE_DIR or cwd-name>/.crewai_user.json`. If
that acquisition raises, the caller's `except Exception` handler logs it
and calls `mark_first_execution_done()` **again** -- a second, unguarded
120s attempt outside any try/except -- so a single contended lock can cost
up to ~4 minutes before anything surfaces. Confirmed by reading
`crewai_core/lock_store.py` and `first_time_trace_handler.py` directly
(paths above, installed version 1.15.21).

**Fix applied** (`backend/Dockerfile`): pre-seed that state file at image
build time by calling the library's own `mark_first_execution_done()`
once, as the runtime user, with `CREWAI_STORAGE_DIR` pinned to a fixed
name (so the build-time path matches the runtime path regardless of
`$HOME`/cwd quirks). Confirmed via `docker compose logs worker`: the
"Tracing Preference Saved" console box (a symptom of this flow running)
disappeared after the fix -- so this specific stall is closed.

**Not fully closed, and NOT the same mechanism as first suspected**: after
the fix, a fresh job with the same bad key *still* stalls the same way
(99% CPU, silent) following the same 401 errors. Re-reading
`crewai/events/listeners/tracing/trace_listener.py` (`TraceCollectionListener
.setup_listeners()`) directly answers whether this second stall could still
be the tracing/lock code: `setup_listeners()` early-returns without
registering ANY handlers (including the `CrewKickoffFailedEvent` handler
that calls `handle_execution_completion()`) when
`should_enable_tracing()` is False AND not first-time AND not TUI mode --
which is exactly this app's state post-fix (`CREWAI_TRACING_ENABLED=false`
+ the pre-seeded "not first execution" file). So the tracing/lock path is
provably fully inert now, on every run, for any failure reason -- the
original diagnosis is genuinely closed, not just closed for the one repro
tried.

The **second stall is therefore something else entirely**, not yet
root-caused (a `[CrewAIEventsBus] Warning: Event pairing mismatch.
'llm_call_failed' closed 'flow_started' (expected 'llm_call_started')`
appears right before the silence starts each time -- still the best lead,
but it's a different subsystem than the tracing listener; worth checking
`crewai/flow/` and the LLM retry/guardrail path in `crewai/llm.py` /
`crewai/task.py` next, not the tracing listener again). Given the time
already sunk into one internals dive, the pragmatic mitigation was to
bound it rather than keep chasing it: `task_soft_time_limit=720` /
`task_time_limit=780` in `backend/app/core/celery_app.py` guarantee any
job that reaches this state fails cleanly (with the app's own friendly
error message -- `SoftTimeLimitExceeded` subclasses `Exception`, so the
task's own handler catches it) within ~12-13 minutes instead of hanging
forever. **This only triggers on a broken/invalid LLM API key** -- a
correctly configured deployment (real `OPENAI_API_KEY`) never reaches this
failure path at all, since the LLM calls simply succeed.

Given this, driving the "completed" state for the screenshot/skill used
`mock-get` (the driver's client-side network-mock command) against a real
submitted job rather than waiting out a real OpenAI call (no paid key was
available in this environment) -- see SKILL.md's "Run (agent path)".

## Two more real bugs, found while driving the UI end-to-end

- **nginx `proxy_pass` + a variable upstream drops the extra URI segment.**
  To survive `docker compose up --force-recreate backend` (which gives the
  backend container a new IP that nginx would otherwise cache forever),
  `nginx.frontend.conf` was changed to resolve the backend name via a
  variable (`set $backend_upstream backend:8000;` + a `resolver` directive).
  That part worked -- but combining a variable with a URI in the same
  `proxy_pass` (`proxy_pass http://$backend_upstream/api/;`) does NOT get
  nginx's usual location-prefix rewrite (that only applies when the
  proxy_pass target is a literal string). `POST /api/jobs` arrived at the
  backend as `POST /api/` -- the `jobs` segment silently vanished, giving a
  404 with no other clue. Fixed by dropping the URI entirely
  (`proxy_pass http://$backend_upstream;`), which forwards the original
  request path unchanged -- correct here since the backend's own routes
  already carry their full path.
- **SQLAlchemy's `Enum(..., native_enum=False)` stores the Python enum
  *member name*, not its `.value`.** Seeding a demo "completed" job by hand
  via `psql` with `status='completed'` (the `JobStatus.COMPLETED` value)
  caused a 500 on every subsequent read (`LookupError: 'completed' is not
  among the defined enum values... Possible values: PENDING, EXTRACTING,
  ...`). Needed `status='COMPLETED'` (the member name) instead. Purely a
  seeding mistake -- the ORM itself always reads/writes consistently; this
  only bites raw SQL that bypasses it.

Both are in SKILL.md's Gotchas/Troubleshooting sections too.

## Confirmed working end-to-end with real API keys

With real `OPENAI_API_KEY` + `SERPER_API_KEY`, submitted two real jobs
(Wikipedia's Solar System and Jupiter articles) through both the raw API
and the actual browser UI. Both completed cleanly in ~40-50s
(pending -> extracting -> analyzing -> researching -> summarizing ->
completed), no hang, no retries, real Serper-sourced citations in the
output with accurate verification notes. The crewai hang discussed above
never triggers when the LLM calls simply succeed, which is the normal
case with a valid key -- confirms the earlier "only fires on LLM
failure" diagnosis. Screenshots in `sessions/real/screenshots/`.
