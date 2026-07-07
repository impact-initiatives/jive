#Step1: Builder Stage
FROM python:3.12-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /uvx /bin/

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN git clone --depth 100 --filter=blob:none --no-checkout https://github.com/impact-initiatives/argus.git /argus && \
    cd /argus && \
    git fetch origin --tags && \
    LATEST_TAG=$(git describe --tags $(git rev-list --tags --max-count=1)) && \
    git checkout $LATEST_TAG && \
    cd .. && \
    uv pip install --system --no-cache /argus

COPY ./pyproject.toml .
COPY ./uv.lock .
RUN uv pip install .

FROM python:3.12-slim-trixie AS runner

WORKDIR /app
RUN mkdir -p /app/logs /app/dataset_config

# Copy the pre-compiled virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Run as a non-root user
RUN useradd --create-home --no-log-init jive

# Copy JIVE microservice code
COPY --chown=jive:jive ./ /app

USER jive

#Default: ingress. Override via Container App command for worker.
#Ingress:  uvicorn main:app --host 0.0.0.0 --port 8000
#Worker:   python worker.py
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
