"""
Onboarding Tool:
Fetch GDT Service Desk field definitions.

Targets the service desk and request type defined in .env (SERVICEDESK_ID / REQUEST_TYPE_ID).
Prod reference: portal 8, request type 10183 (RQA Servicedesk)
Dev target   : portal 40, request type 10216 (GDT-HQ)

Outputs:
  - Request type metadata and visible fields (JSM API)
  - Full issue type field schema (Jira REST API)
  - Saved to data/ as JSON for reference

Usage:
  uv run python scripts/fetch_fields.py
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from rich.console import Console
from rich.table import Table

load_dotenv()

JIRA_URL = os.environ.get("JIRA_BASE_URL", "https://reach-initiative.atlassian.net").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_API_EMAIL")
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN")

# Default service desk IDs
SERVICEDESK_ID = os.environ.get("SERVICEDESK_ID", "40")
REQUEST_TYPE_ID = os.environ.get("REQUEST_TYPE_ID", "10216")
PROD_SERVICEDESK_ID = os.environ.get("PROD_SERVICEDESK_ID", "8")
PROD_REQUEST_TYPE_ID = os.environ.get("PROD_REQUEST_TYPE_ID", "10183")

if not JIRA_EMAIL or not JIRA_TOKEN:
    print("[Error] JIRA_API_EMAIL and JIRA_API_TOKEN must be set in .env")
    sys.exit(1)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
HEADERS = {"Accept": "application/json"}
OUTPUT_DIR = Path(__file__).parent.parent / "data"

console = Console()


def get(path: str) -> dict:
    url = f"{JIRA_URL}{path}"
    resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def save(filename: str, data: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    console.print(f"[dim]Saved → {path}[/dim]")


def fetch_servicedesk_info() -> dict:
    console.rule("[bold]Service Desk Info")
    data = get(f"/rest/servicedeskapi/servicedesk/{SERVICEDESK_ID}")
    console.print(f"  ID          : {data.get('id')}")
    console.print(f"  Project key : {data.get('projectKey')}")
    console.print(f"  Name        : {data.get('projectName')}")
    save("servicedesk_info.json", data)
    return data


def fetch_request_types() -> list:
    console.rule("[bold]Request Types (portal)")
    data = get(f"/rest/servicedeskapi/servicedesk/{SERVICEDESK_ID}/requesttype")
    request_types = data.get("values", [])

    table = Table("ID", "Name", "Description")
    for rt in request_types:
        table.add_row(str(rt.get("id")), rt.get("name", ""), rt.get("description", ""))
    console.print(table)
    save("request_types.json", data)
    return request_types


def fetch_request_type_fields(servicedesk_id: str, request_type_id: str, label: str, filename: str) -> dict:
    console.rule(f"[bold]Fields for Request Type {request_type_id} ({label})")
    data = get(
        f"/rest/servicedeskapi/servicedesk/{servicedesk_id}"
        f"/requesttype/{request_type_id}/field?expand=field"
    )
    fields = data.get("requestTypeFields", [])

    table = Table("Field ID", "Name", "Required", "Type")
    for f in fields:
        jira_field = f.get("jiraSchema", {})
        table.add_row(
            f.get("fieldId", ""),
            f.get("name", ""),
            "✓" if f.get("required") else "",
            jira_field.get("type", "") or jira_field.get("custom", ""),
        )
    console.print(table)
    save(filename, data)
    return data


def fetch_issue_createmeta(project_key: str) -> dict:
    console.rule(f"[bold]Issue Create Meta (project {project_key})")
    data = get(
        f"/rest/api/3/issue/createmeta"
        f"?projectKeys={project_key}&issuetypeIds={REQUEST_TYPE_ID}"
        f"&expand=projects.issuetypes.fields"
    )
    save("issue_createmeta.json", data)

    # Flatten and display fields
    projects = data.get("projects", [])
    if not projects:
        console.print("[yellow]No createmeta found for this project/issuetype[/yellow]")
        return data

    for project in projects:
        for issuetype in project.get("issuetypes", []):
            console.print(f"  Issue type: {issuetype.get('name')} (id={issuetype.get('id')})")
            fields = issuetype.get("fields", {})
            table = Table("Field ID", "Name", "Required", "Schema type")
            for field_id, field_def in fields.items():
                schema = field_def.get("schema", {})
                table.add_row(
                    field_id,
                    field_def.get("name", ""),
                    "✓" if field_def.get("required") else "",
                    schema.get("type", "") or schema.get("custom", ""),
                )
            console.print(table)
    return data


def main():
    console.print(f"\n[bold green]JIVE - Phase 1: GDT Service Desk Field Exploration[/bold green]")
    console.print(f"  URL  : {JIRA_URL}")
    console.print(f"  User : {JIRA_EMAIL}")
    console.print(f"  Portal {SERVICEDESK_ID} › Request type {REQUEST_TYPE_ID}\n")

    # 1. Service desk metadata
    sd_info = fetch_servicedesk_info()
    project_key = sd_info.get("projectKey", "")

    # 2. All request types in the portal
    fetch_request_types()

    # 3. Dev GDT fields
    fetch_request_type_fields(SERVICEDESK_ID, REQUEST_TYPE_ID, "GDT dev", "request_type_fields_dev.json")

    # 4. Prod RQA fields (all visible form fields)
    try:
        fetch_request_type_fields(PROD_SERVICEDESK_ID, PROD_REQUEST_TYPE_ID, "RQA prod", "request_type_fields_prod.json")
    except Exception as e:
        console.print(f"[yellow]Could not fetch prod fields: {e}[/yellow]")

    # 5. Full field schema from Jira REST (agent-facing + hidden fields)
    if project_key:
        fetch_issue_createmeta(project_key)
    else:
        console.print("[yellow]Skipping createmeta — project key not found[/yellow]")

    console.print("\n[bold green]Done.[/bold green] Check data/ for full JSON output.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        console.print(f"[red]HTTP error: {e.response.status_code} — {e.response.text}[/red]")
        sys.exit(1)
    except KeyError as e:
        console.print(f"[red]Missing env variable: {e}[/red]")
        console.print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
