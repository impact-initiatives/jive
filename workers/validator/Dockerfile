FROM python:3.14-slim-trixie AS runner
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV UV_NO_DEV=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY workers/validator/ /app/workers/validator/
COPY common/argus/ /app/common/argus/
COPY common/jira/ /app/common/jira/
COPY common/jive_logging/ /app/common/jive_logging/
COPY common/worker_base/ /app/common/worker_base/

WORKDIR /app

RUN uv sync --locked --directory workers/validator

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/logs /app/dataset_config

# Run as a non-root user
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs /app/dataset_config 
USER jive

CMD ["python", "-m", "validator.main"]

