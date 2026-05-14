# JIVE — Jira IMPACT Validation Engine

**JIVE** (Jira IMPACT Validation Engine) is an asynchronous, event-driven tool that automates RQA workflow. It bridges Jira Service Desk with the rqa-validator engine to automatically download submitted datasets, run validation pipelines and post structured error reports back to the Jira ticket.


## Overview

Research data collected through household surveys, market assessments, and key informant interviews undergoes a rigorous quality assurance process before it can be published. Historically, this process was manual: country teams would run validation scripts locally, interpret the output, and post summary results through Excel file sent by email, Microsoft Teams chat and now in Jira tickets. This is slow, error-prone, and creates a bottleneck that delays data publication.

JIVE aims to automate this workflow freeing capacity of country teams and RQA to focus on more research related tasks. It acts as an asynchronous, event-driven tool that bridges the new **RQA Jira Service Desk** with the [`rqa-validator`](https://github.com/gim-am/rqa-validator) data quality engine (planned move to [Impact Initiatives' GitHub](https://github.com/impact-initiatives/rqa-validator)). When a country team member submits a dataset for review via a Jira ticket, JIVE automatically downloads the file, runs the full validation pipeline, generates a report, and posts a structured summary comment directly on the ticket.

### Asynchronous design

Data validation can be computationally expensive. A single dataset can contain from hundreds to thousands of rows across multiple sheets, requiring cross-referencing against cleaning logs, schema definitions, and categorical choice lists. Validation can take time depending on the size of the dataset. If this ran synchronously inside a Jira webhook handler (max 20s response time), the HTTP connection would time out and Jira would register a failure or not acknowledge at all the webhook.

JIVE solves this by decoupling ingestion from processing using an Azure Storage Queue. The webhook handler returns immediately (`HTTP 202 Accepted`), and a background worker processes the job asynchronously. The queue is monitored and scaled, scaling the worker containers from zero when no jobs are present and scaling up as jobs are added (the system incurs no additional compute cost when no jobs are queued).

## Architecture

```
                          ┌──────────────────────┐
                          │  Jira Automation Rule │
                          └──────────┬───────────┘
                                     │ POST /api/webhook
                                     ▼
                          ┌──────────────────────┐
                          │  jive-ingress         │
                          │  (FastAPI · main.py)  │
                          └──────────┬───────────┘
                                     │ Enqueue message
                                     ▼
                          ┌──────────────────────┐
                          │  Azure Storage Queue  │
                          │  (KEDA-monitored)     │
                          └──────────┬───────────┘
                                     │ Scale-to-zero
                                     ▼
                          ┌────────────────────────┐
                          │  jive-worker           │
                          │  (worker.py)           │
                          │                        │
                          │  1. Download dataset   │
                          │  2. Run rqa-validator  │
                          │  3. Upload report      │
                          │  4. Post ADF comment   │
                          └────────────────────────┘
```

Both services run from the same Docker image with different entrypoint commands, deployed as separate Azure Container Apps (ACR).

## Project Structure

```
jira_poc/
├── main.py                  FastAPI ingress — webhook endpoint
├── worker.py                Queue consumer — orchestrates validation lifecycle
├── jira_client.py           Jira REST API client
├── models.py                Pydantic models for inbound Jira webhook payloads
├── report_formatter.py      Transforms PipelineResponse into Atlassian Document Format (ADF)
├── logger.py                JSON-structured logging for Azure Log Analytics
├── excel_exporter.py        Generates multi-sheet Excel validation reports
├── Dockerfile               Build image for acr and container apps
├── pyproject.toml           Dependencies and project metadata
├── tests/
│   ├── test_models.py                Payload validation and normalization tests
│   ├── test_report_formatter.py      ADF output structure tests
│   ├── test_webhook.py               FastAPI endpoint integration tests
│   └── test_secure_link_integration.py  End-to-end secure link workflow tests
└── infra/
    ├── main.bicep            Bicep orchestrator for all Azure resources
    └── modules/              Individual resource definitions (ACR, Storage, Key Vault, etc.)
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure CLI (for deployment and Key Vault access)
- Docker (for image builds)

## Local Development

### Install dependencies

```bash
uv sync --extra dev
```

### Environment variables

Create a `.env` file in the project root with the following variables:

| Variable | Required | Description |
|---|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Yes | Azure Storage Account connection string |
| `JIVE_QUEUE_NAME` | No | Queue name (default: `jive-validation-queue`) |
| `JIVE_API_KEY` | Yes | Shared secret for authenticating Jira webhooks |
| `JIRA_API_EMAIL` | Yes | Jira service account email |
| `JIRA_API_TOKEN` | Yes | Jira API token for the service account |
| `JIRA_BASE_URL` | No | Jira instance URL (default: `https://reach-initiative.atlassian.net`) |
| `JIVE_MAX_RETRIES` | No | Max retries before dead-lettering a message (default: `3`) |
| `SECURE_LINK_USERNAME` | No | Basic auth username for secure link downloads |
| `SECURE_LINK_PASSWORD` | No | Basic auth password for secure link downloads |

### Start the local queue emulator

Use [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) to emulate Azure Storage Queues locally:

```bash
npm install -g azurite
azurite-queue --queueHost 127.0.0.1
```

Set `AZURE_STORAGE_CONNECTION_STRING` to the Azurite default connection string.

##### Run the ingress

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

##### Run the worker

```bash
uv run python worker.py
```

##### Run test

```bash
uv run pytest tests/ -v 2>&1
uv run ruff check .
```

### Deployment

Infrastructure is defined in Bicep and deployed via GitHub Actions. See [`NOTION_CICD_INFRASTRUCTURE.md`](./NOTION_CICD_INFRASTRUCTURE.md) for the complete workflow documentation (need to add it)fo.

#### Manual deployment

```bash
# Deploy infrastructure
az deployment group create \
  --resource-group rg-impact-etl \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam

# Build Docker image (retrieves GitHub PAT securely from Azure Key Vault)
export GITHUB_PAT=$(az keyvault secret show \
  --name "github-pat" \
  --vault-name "<your-keyvault-name>" \
  --query value -o tsv)
docker build --secret id=github_token,env=GITHUB_PAT \
  -t jiveacr.azurecr.io/jive:latest .
docker push jiveacr.azurecr.io/jive:latest

# Update Container Apps
az containerapp update --name jive-ingress \
  --resource-group rg-impact-etl \
  --image jiveacr.azurecr.io/jive:latest
az containerapp update --name jive-worker \
  --resource-group rg-impact-etl \
  --image jiveacr.azurecr.io/jive:latest
```

## Roadmap

- [ ] Upload validation reports to Azure Blob Storage and include a SAS download link in the Jira comment instead of attaching the file directly (avoids Jira attachment size limits)
- [ ] Transition the Jira ticket to a target status automatically based on validation results (e.g., move to "Approved" on pass (default: JIRA_TRANSITION_APPROVED), "Needs Revision" on fail (default: JIRA_TRANSITION_REVISION))
- [ ] Add support for multiple dataset types beyond JMMI (MSNA, ESNFI) with automatic schema detection
- [ ] Implement Azure Managed Identity for Key Vault secret retrieval at runtime, removing the need for connection strings in environment variables


## Related Repositories

- [`rqa-validator`](https://github.com/impact-initiatives/rqa-validator) — The core data validation engine
