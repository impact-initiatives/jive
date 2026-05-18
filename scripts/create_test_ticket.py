"""
Onboarding & Testing Tool:

Create a test ticket in GDT dev service desk, mirroring the RQA prod ticket structure.

RQA prod reference (request type 10183):
  - summary: "What is the RCID and type of output that you need to publish or archive?"
  - example: "UKR2401 JMMI R40 Factsheet"

GDT dev target: serviceDesk 40, requestType 10216

Usage:
  uv run python scripts/create_test_ticket.py [summary]
"""

import os
import sys

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from rich.console import Console

load_dotenv()

JIRA_URL = os.environ.get("JIRA_BASE_URL", "https://reach-initiative.atlassian.net").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_API_EMAIL")
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN")

SERVICEDESK_ID = os.environ.get("SERVICEDESK_ID", "40")
REQUEST_TYPE_ID = os.environ.get("REQUEST_TYPE_ID", "10216")

if not JIRA_EMAIL or not JIRA_TOKEN:
    print("[Error] JIRA_API_EMAIL and JIRA_API_TOKEN must be set in .env")
    sys.exit(1)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
DEFAULT_SUMMARY = "UKR2401 JMMI R40 Factsheet"

console = Console()


def create_ticket(summary: str) -> dict:
    url = f"{JIRA_URL}/rest/servicedeskapi/request"
    payload = {
        "serviceDeskId": SERVICEDESK_ID,
        "requestTypeId": REQUEST_TYPE_ID,
        "requestFieldValues": {
            "summary": summary,
        },
    }
    resp = requests.post(url, json=payload, auth=AUTH, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def main():
    summary = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SUMMARY

    console.print(f"\n[bold green]JIVE - Create Test Ticket (GDT dev)[/bold green]")
    console.print(f"  Summary : [cyan]{summary}[/cyan]\n")

    ticket = create_ticket(summary)
    issue_key = ticket.get("issueKey", "")
    console.print(f"[green]✓ Created → {issue_key}[/green]")
    console.print(f"  {JIRA_URL}/browse/{issue_key}")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        console.print(f"[red]HTTP {e.response.status_code}: {e.response.text}[/red]")
        sys.exit(1)
