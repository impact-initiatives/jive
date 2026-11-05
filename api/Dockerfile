FROM python:3.14-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV UV_NO_DEV=1
COPY . /app
WORKDIR /app

RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/logs 
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs 

USER jive

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


