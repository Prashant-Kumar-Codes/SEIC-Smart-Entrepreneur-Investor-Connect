# ─────────────────────────────────────────────────────────
# Gunicorn Configuration — Business Inspector
# Optimized for low-memory VPS with fast response times
# ─────────────────────────────────────────────────────────

import multiprocessing

# ── Server Socket ────────────────────────────────────────
bind = "0.0.0.0:8000"

# ── Worker Processes ─────────────────────────────────────
# 2 workers keeps memory low while handling concurrent requests.
# gthread uses threads instead of forking — ~40% less RAM than sync.
workers = 2
worker_class = "gthread"
threads = 4  # 2 workers × 4 threads = 8 concurrent requests

# ── Timeouts ─────────────────────────────────────────────
timeout = 120       # Allow slow ML predictions to complete
graceful_timeout = 30
keepalive = 5

# ── Memory Management ───────────────────────────────────
# Recycle workers after N requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# ── Performance ─────────────────────────────────────────
# Load app ONCE before forking workers → shared memory, NO cold start
preload_app = True

# ── Logging ─────────────────────────────────────────────
accesslog = "-"          # stdout
errorlog = "-"           # stderr
loglevel = "info"

# ── Process Naming ──────────────────────────────────────
proc_name = "business-inspector"
