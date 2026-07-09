


#Step1: Builder Stage
FROM python:3.12-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /uvx /bin/

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app
RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/logs /app/dataset_config
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs /app/dataset_config

USER jive

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


