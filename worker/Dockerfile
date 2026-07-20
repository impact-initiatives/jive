#Step1: Builder Stage
FROM python:3.12-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
ENV UV_NO_DEV=1
ARG RELEASE_TAG

WORKDIR /build
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN git clone --depth 100 --filter=blob:none --no-checkout https://github.com/impact-initiatives/argus.git /argus && \
    cd /argus && \
    git fetch origin --tags && \
    LATEST_TAG=$(git describe --tags $(git rev-list --tags --max-count=1)) && \
    git checkout $LATEST_TAG && \
    echo "$LATEST_TAG" > /argus_version.txt && \
    cd ..  && \
    uv pip install --no-cache /argus

RUN echo ${RELEASE_TAG} > /jive_version.txt

COPY ./ ./

# remove local reference to argus in toml file
RUN sed -e '/^\[tool\.uv\.sources\]$/d' -e '/^argus = { path =/d' pyproject.toml > pyproject.toml.tmp && \
    mv pyproject.toml.tmp pyproject.toml
    
RUN uv pip install .

FROM python:3.12-slim-trixie AS runner

WORKDIR /app

COPY --from=builder /argus_version.txt /app/argus_version.txt
COPY --from=builder /jive_version.txt /app/jive_version.txt
# must be consistent with env variables in azure.
ENV ARGUS_VERSION_FILE=/app/argus_version.txt
ENV JIVE_VERSION_FILE=/app/jive_version.txt


RUN mkdir -p /app/logs /app/dataset_config

# Copy the pre-compiled virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Run as a non-root user
RUN useradd --create-home --no-log-init jive

# Copy JIVE worker microservice code
COPY --chown=jive:jive . /app
RUN chown -R jive:jive /app/logs /app/dataset_config
USER jive

CMD ["python", "-m", "worker.main"]
