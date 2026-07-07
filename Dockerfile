#Step1: Builder Stage
FROM python:3.12-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /uvx /bin/

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 100 --filter=blob:none --no-checkout https://github.com/impact-initiatives/argus.git /tmp/argus && \
    cd /tmp/argus && \
    git fetch origin --tags && \
    LATEST_TAG=$(git describe --tags $(git rev-list --tags --max-count=1)) && \
    git checkout $LATEST_TAG && \
    uv pip install --system --no-cache . && \
    cd / && \
    rm -rf /tmp/argus

# Install jive dependencies
RUN uv pip install --system --no-cache \
    fastapi>=0.111.0 \
    uvicorn>=0.30.1 \
    requests>=2.32.3 \
    pydantic>=2.8.2 \
    azure-storage-queue>=12.10.0 \
    tenacity>=8.2.0 \
    polars>=1.0.0 \
    xlsxwriter>=3.2.0

COPY . /app


#Step 2: Runtime Stage
FROM python:3.12-slim-trixie

#Run as a non-root user
RUN useradd --create-home --no-log-init jive

#Copy Python packages and app code from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

 
# Copy JIVE microservice code
COPY --chown=jive:jive . /app

WORKDIR /app
RUN mkdir -p /app/logs /app/dataset_config
USER jive

#Default: ingress. Override via Container App command for worker.
#Ingress:  uvicorn main:app --host 0.0.0.0 --port 8000
#Worker:   python worker.py
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
