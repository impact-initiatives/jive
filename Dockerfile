#Step1: Builder Stage
FROM python:3.12-slim-trixie AS builder 

COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /uvx /bin/

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Clone rqa-validator and install it as a proper package and all of its dependencies
RUN --mount=type=secret,id=github_token,required=true \
    git clone https://$(cat /run/secrets/github_token)@github.com/impact-initiatives/rqa-validator.git /tmp/rqa-validator && \
    uv pip install --system --no-cache /tmp/rqa-validator && \
    rm -rf /tmp/rqa-validator

# Install jira_poc dependencies
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

#Copy Python packages and app code from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /app /app

WORKDIR /app

#Run as a non-root user
RUN useradd --create-home --no-log-init jive
USER jive

#Default: ingress. Override via Container App command for worker.
#Ingress:  uvicorn main:app --host 0.0.0.0 --port 8000
#Worker:   python worker.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
