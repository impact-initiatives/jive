import os
import time
import secrets
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.queue import QueueClient
from models import JiraSubmissionPayload
from logger import get_logger

logger = get_logger("jive.ingress")

app = FastAPI(title="JIVE Ingress Webhook")

QUEUE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
QUEUE_NAME = os.getenv("JIVE_QUEUE_NAME", "jive-validation-queue")
API_KEY = os.getenv("JIVE_API_KEY", "")


def get_queue_client() -> QueueClient:
    if not QUEUE_CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not set")
    return QueueClient.from_connection_string(
        conn_str=QUEUE_CONNECTION_STRING,
        queue_name=QUEUE_NAME,
    )


@app.get("/healthz")
async def health_check():
    """Liveness probe endpoint for Azure Container Apps."""
    return {"status": "ok"}


@app.post("/api/webhook")
def handle_jira_webhook(
    payload: JiraSubmissionPayload,
    x_functions_key: str = Header(None),
):
    """
    Ingress endpoint for Jira Automation.
    Validates the API Key, validates the payload via Pydantic, and pushes to the Azure Storage Queue.
    Returns 202 Accepted immediately to prevent Jira timeouts.
    """
    start = time.monotonic()

    #Authenticate Request
    if not x_functions_key or not secrets.compare_digest(x_functions_key, API_KEY):
        logger.warning(
            "Unauthorized request",
            extra={"issue_key": payload.issue_key, "status_code": 401},
        )
        raise HTTPException(status_code=401, detail="Invalid API Key")

    #Push message to Azure Storage Queue
    try:
        queue_client = get_queue_client()
        message_body = payload.model_dump_json()
        queue_client.send_message(message_body)
    except Exception as e:
        logger.error(
            "Failed to enqueue message",
            exc_info=e,
            extra={"issue_key": payload.issue_key},
        )
        raise HTTPException(status_code=500, detail="Failed to enqueue validation job")

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Job queued",
        extra={"issue_key": payload.issue_key, "status_code": 202, "duration_ms": duration_ms},
    )

    #Return 202 Accepted
    return JSONResponse(
        status_code=202,
        content={"status": "Accepted", "message": f"Job queued for issue {payload.issue_key}"},
    )
