# Shared base image for both the API and the Celery worker (see
# docker-compose.yml, which runs this same image with two different
# commands). Keeping one image avoids dependency drift between them.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies:
#   ffmpeg        -> audio/video extraction & transcoding
#   tesseract-ocr  -> OCR fallback for image-only (scanned) PDFs
#   poppler-utils  -> renders PDF pages to images for the OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Placed after the pip-install layer (not in the first ENV block) so tweaking
# these later doesn't invalidate the slow dependency-install cache.
ENV CREWAI_STORAGE_DIR=research_summarize \
    CREWAI_TRACING_ENABLED=false

RUN mkdir -p /app/data/uploads \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Pre-seed crewai's own "first execution" state file so a fresh container
# never hits its interactive first-run tracing-consent flow at request time.
# That flow is otherwise harmless when skipped (stdin isn't a tty, so the
# actual prompt is skipped) -- but a file-lock acquisition inside the same
# code path (crewai_core's portalocker-based lock, 120s timeout, and a
# retry-on-exception path that can double that) was observed to stall a
# worker for minutes on its very first task in this environment. Running it
# once, here, with a throwaway key, means every real request skips it
# entirely. See the run skill's Gotchas for the full diagnosis.
RUN OPENAI_API_KEY=sk-build-time-placeholder python -c \
    "from crewai.events.listeners.tracing.utils import mark_first_execution_done; mark_first_execution_done(user_consented=False)"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
