# BITHub chat API — production image.
#
# BUILD CONTEXT IS THE REPO ROOT, not chatbot/:
#     docker build -f deploy/Dockerfile -t bithub-chat .
# because chatbot/remote_loader.py does `import data_pb2`, and data_pb2.py
# lives in pipeline/. Building from chatbot/ alone fails at import.

FROM python:3.13-slim

# curl is for the platform health check only; no compiler is needed because
# every wheel below is manylinux prebuilt.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Dependencies first so code edits do not invalidate the layer.
COPY deploy/requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# The backend, and the one file it reaches for outside its own directory.
COPY chatbot/ /srv/chatbot/
COPY pipeline/data_pb2.py /srv/pipeline/data_pb2.py

# Bake the ~15 MB bundle index into the image.
#
# main.py downloads this from CloudFront at MODULE IMPORT time and raises
# SystemExit if the download fails — in a container that is a boot crash, and
# on a scale-to-zero platform every cold start would pay the download again.
# Shipping it means the container boots without network and starts warm.
# Refresh it by running the service once locally and re-copying chatbot/cache/.
COPY chatbot/cache/ /srv/chatbot/cache/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BITHUB_CACHE_DIR=/srv/chatbot/cache

# No frontend build in the image: GitHub Pages serves the site. The
# StaticFiles mount at "/" in main.py is simply inactive when the directory
# is absent, which is what we want for an API-only deployment.
ENV BITHUB_FRONTEND_BUILD=/srv/nonexistent

WORKDIR /srv/chatbot

# One worker on purpose. The rate limiter in main.py (_ip_hits, _day_hits) is
# in-process, so every extra worker or replica multiplies the real cap by that
# count. Concurrency comes from async I/O; the agent loop is network-bound on
# Anthropic, not CPU-bound.
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "310"]
