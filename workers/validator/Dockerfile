#Step1: Builder Stage
FROM python:3.14-slim-trixie AS builder 

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# get latest jive release tag which is what this is building
RUN TAG=$(curl -fsSL https://api.github.com/repos/impact-initiatives/jive/releases/latest \
    | awk -F'"' '/"tag_name"/ {print $4; exit}') && \
    test -n "$TAG" && \
    echo "JIVE tag: $TAG" && \
    echo "$TAG" > /jive_version.txt && \

FROM python:3.14-slim-trixie AS runner
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
ENV UV_NO_DEV=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
COPY workers/validator/ /app/workers/validator/
COPY common/argus/ /app/common/argus/
WORKDIR /app

RUN uv sync --locked --directory workers/validator

ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /jive_version.txt /app/jive_version.txt
# must be consistent with env variables in azure.
ENV JIVE_VERSION_FILE=/app/jive_version.txt


RUN mkdir -p /app/logs /app/dataset_config

# Run as a non-root user
RUN useradd --create-home --no-log-init jive
RUN chown -R jive:jive /app/logs /app/dataset_config 
USER jive

CMD ["python", "-m", "validator.main"]

