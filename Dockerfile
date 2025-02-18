FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update -qy
RUN apt-get install -qyy -o APT::Install-Recommends=false -o APT::Install-Suggests=false ca-certificates \
    git wget

WORKDIR /app

RUN --mount=type=secret,id=netrc,target=/root/.netrc,mode=0600 \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=./uv.lock,target=uv.lock \
    --mount=type=bind,source=./pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=./.python-version,target=.python-version \
    uv sync --frozen --no-dev --no-install-project

COPY . /app

FROM python:3.12-slim-bookworm

# Install cron
RUN apt-get update && apt-get install -y cron

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:${PYTHONPATH:-}"

WORKDIR /app
# Add cron job to execute daily_ingest.py every day at 00:00
RUN echo "0 0 * * * python /app/app/daily_ingest.py" > /etc/cron.d/daily_ingest
RUN chmod 0644 /etc/cron.d/daily_ingest && crontab /etc/cron.d/daily_ingest
RUN touch /var/log/cron.log && tail -f /var/log/cron.log &
RUN service cron start

# Start cron and the main app
CMD service cron start && python app/main.py