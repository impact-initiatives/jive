FROM python:3.14-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV UV_NO_DEV=1
COPY api/ /app/api
COPY common/jive_logging/ /app/common/jive_logging/

WORKDIR /app

RUN uv sync --locked --directory api

ENV PATH="/app/api/.venv/bin:$PATH"

RUN mkdir -p /app/logs 
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs 

USER jive

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


