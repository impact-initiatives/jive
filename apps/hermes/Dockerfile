FROM python:3.14-slim-trixie AS runner
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV UV_NO_DEV=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY apps/hermes/ /app/apps/hermes
COPY common/argus/ /app/common/argus/
COPY common/argus_schemas/ /app/common/argus_schemas/
COPY common/jive_logging/ /app/common/jive_logging/

WORKDIR /app

RUN uv sync --locked --directory apps/hermes

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/logs 

# Run as a non-root user
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs 
USER jive
EXPOSE 8501
# HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
WORKDIR /app/apps/hermes
ENTRYPOINT ["streamlit", "run", "src/hermes", "--server.port=8501", "--server.address=0.0.0.0"]
