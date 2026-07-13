# JIVE — Jira IMPACT Validation Engine

**JIVE** (Jira IMPACT Validation Engine) is an asynchronous, event-driven microservice that automates Research Quality Assurance (RQA) workflows. It bridges the Jira Service Management (JSM) portal with the [Argus](https://github.com/impact-initiatives/argus) engine to automatically download submitted datasets, execute validation pipelines, generate Excel reports, and post structured Atlassian Document Format (ADF) comments back to Jira tickets.

## Overview

Research data collected through household surveys, market assessments, and key informant interviews undergoes rigorous quality assurance before publication. Historically, this involved manual scripts, downloading files, interpreting output, and back-and-forth communication on Teams or email.

JIVE automates this bottleneck. When a country team member submits a dataset for review via a Jira ticket, JIVE automatically:
1. Receives the webhook event from Jira.
2. Extracts dataset context (dataset type, secure links) from Jira ProForma forms.
3. Downloads the dataset securely.
4. Executes the full `ARGUS` pipeline.
5. Generates a multi-sheet Excel report detailing all errors, warnings, and info messages.
6. Posts a formatted summary comment directly on the Jira ticket and attaches the Excel report.

### The Asynchronous Queue Architecture

Data validation is computationally expensive. Datasets can contain hundreds of thousands of rows across multiple sheets, requiring cross-referencing against cleaning logs and complex schema definitions. If this ran synchronously inside a Jira webhook handler (which requires a response within seconds), the HTTP connection would time out and fail.

JIVE solves this by **decoupling ingestion from processing** using Azure Storage Queues and Azure Container Apps:
- **Ingress**: A lightweight FastAPI gateway immediately returns `HTTP 202 Accepted` to Jira and pushes the payload to the queue.
- **Worker**: A background python worker asynchronously pulls jobs from the queue. Leveraging **KEDA** (Kubernetes Event-driven Autoscaling), the worker container scales down to 0 when idle (costing nothing) and scales out dynamically based on the queue length.

---

## Architecture

```mermaid
flowchart TD
    JSM[Jira Service Management] -->|1. Submit Portal Form| WH(Webhook Trigger)
    WH -->|2. POST Payload| ING["JIVE Ingress (FastAPI)"]
    
    subgraph Azure Container Apps
        ING -->|3. Enqueue| Q[(Azure Storage Queue)]
        Q -->|4. Dequeue| WRK["JIVE Worker (Python)"]
    end
    
    WRK <-->|5. Fetch ProForma Context| JSM
    WRK <-->|6. Download Dataset| SHP[SharePoint / Secure Link]
    WRK <-->|7. Run Validation| RQA[ARGUS Engine]
    
    WRK -->|8. Attach Excel Report| JSM
    WRK -->|9. Post ADF Comment| JSM
```

---

## Project Structure
Within this project there are two applications: api and worker. Each has its own configuration and deployment files. 

```text

├── api                     FastAPI ingress (webhook endpoint)
├── infra                   Bicep IaC templates for Azure deployment
├── local                   Local exploration and local Docker Compose setup
└── worker                  Queue consumer (orchestrates validation lifecycle)

```

---

## Local Development & Configuration
To set up a local environment for either of the components see their respective readme files:
- [API readme](api/readme.md)
- [Worker readme](worker/readme.md)

### Running the Services Locally

We recommend using the provided `local/docker-compose.yml` to mirror the Azure architecture (FastAPI Gateway + Azurite + Worker). Before running this make sure that `api` and `worker` both have an `.env` file set up. To deploy locally to Docker:

```bash
docker compose -f local/docker-compose.yml up --build
```
* **JIVE Ingress Gateway**: Accessible at `http://localhost:8000/api/webhook`
* **Azurite Emulator**: Emulates Azure Storage Queues at `http://localhost:10001`
* **Background Worker**: Polls Azurite for jobs, executes validation, and interacts with Jira.

Alternatively, you can run them locally via `uv`. See:
- [API readme](api/readme.md)
- [Worker readme](worker/readme.md)

To connect Jira automation components to a locally hosted envrionment an additional service is required to allow Jira to connect to a localhost address. Services like [ngrok](ngrok.com/) can be used for this. 

See this for additional details: [JIVE-ARGUS Demo](https://app.notion.com/p/JIVE-Demo-372e735be74b80cdb994ff0a9d0fbab4)

---

## Azure Cloud Deployment
**Note: This is currently out of date**

The entire infrastructure is defined as Code (IaC) using Azure Bicep located in the `infra/` directory.

### Key Infrastructure Features:
* **Azure Container Apps (ACA)**: Serverless hosting for the Ingress and Worker apps.
* **KEDA Scaling**: The Worker app automatically scales based on the length of the Azure Storage Queue.
* **Security**: System-Assigned Managed Identities are used to pull secrets (Jira API keys, connection strings) directly from **Azure Key Vault**. Secrets are never exposed in environment variables.
* **Observability**: An **Azure Log Analytics** workspace is automatically provisioned and linked to the Container App environment for centralized JSON-structured logging.

### Deployment Commands
```bash
# 1. Deploy all infrastructure (Storage, KeyVault, Container Apps, Log Analytics)
az deployment group create \
  --resource-group rg-impact-etl \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam

# 2. Build and Push Docker Image to Azure Container Registry
az acr build --registry <your-acr-name> --image jive:latest .

# 3. Update Container Apps to use the latest image
az containerapp update --name jive-ingress --resource-group rg-impact-etl --image <your-acr-name>.azurecr.io/jive:latest
az containerapp update --name jive-worker --resource-group rg-impact-etl --image <your-acr-name>.azurecr.io/jive:latest
```
*(Note: Automated CI/CD via GitHub Actions is planned for the near future).*

---

## Roadmap

- [ ] Upload validation reports to Azure Blob Storage and include a SAS download link in the Jira comment instead of attaching the file directly (avoids Jira attachment size limits)
- [ ] Transition the Jira ticket to a target status automatically based on validation results (e.g., move to "Approved" on pass (default: JIRA_TRANSITION_APPROVED), "Needs Revision" on fail (default: JIRA_TRANSITION_REVISION))
- [ ] Add support for multiple dataset types beyond JMMI (MSNA, ESNFI) with automatic schema detection
- [ ] Implement Azure Managed Identity for Key Vault secret retrieval at runtime, removing the need for connection strings in environment variables

---

## Related Repositories
- [`impact-initiatives/argus`](https://github.com/impact-initiatives/argus) — A flexible framework for validating standardised and less-standardised datasets.
- [`impact-initiatives/argus_schemas`](https://github.com/impact-initiatives/argus_schemas) — Configuration files for Argus datasets.
