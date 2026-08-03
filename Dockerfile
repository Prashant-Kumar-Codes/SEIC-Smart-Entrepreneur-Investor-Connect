# ─────────────────────────────────────────────────────────
# SEIC — Smart Entrepreneur Investor Connect
# Production Flask Container — Multi-stage build
# ─────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="Prashant <prashant@prashantbuilds.in>"
LABEL description="SEIC — Smart Entrepreneur Investor Connect | Flask + ML + Gemini AI"

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
WORKDIR /app

COPY . .

RUN python -m compileall -q /app
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]