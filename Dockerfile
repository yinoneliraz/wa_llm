FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /uvx /bin/

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app

# Copy the project into the image
COPY pyproject.toml .
COPY uv.lock .
COPY .env .

RUN uv sync --frozen

# Copy the src directory into the container
COPY src/ ./src

# Presuming there is a `my_app` command provided by the project
CMD ["uv", "run", "src/main.py"]