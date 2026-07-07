import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def debug():
    base_url = os.environ.get("JIRA_BASE_URL").rstrip("/")
    auth = (os.environ.get("JIRA_API_EMAIL"), os.environ.get("JIRA_API_TOKEN"))
    issue_key = "GDT-52"

    print(f"JIRA_BASE_URL: {base_url}")

    # Get Issue ID
    resp = requests.get(f"{base_url}/rest/api/3/issue/{issue_key}?fields=id,description", auth=auth)
    if resp.status_code != 200:
        print(f"[Error] Failed to fetch issue: {resp.status_code} {resp.text}")
        return

    issue_id = resp.json().get("id")
    print(f"[OK] Issue ID: {issue_id}")

    # Get Description just in case
    desc = resp.json().get("fields", {}).get("description")
    print(f"Description: {str(desc)[:100]}...")

    # Test Service Desk API
    sd_url = f"{base_url}/rest/servicedeskapi/request/{issue_key}"
    print(f"Fetching {sd_url}...")
    sd_resp = requests.get(sd_url, auth=auth)
    print(f"Service Desk API Status: {sd_resp.status_code}")
    if sd_resp.status_code != 200:
        print(f"Service Desk API Response: {sd_resp.text}")

    # Check standard attachments
    std_url = f"{base_url}/rest/api/3/issue/{issue_key}?fields=attachment"
    print("Fetching standard attachments...")
    std_resp = requests.get(std_url, auth=auth)
    print(f"Standard API Status: {std_resp.status_code}")
    if std_resp.status_code == 200:
        atts = std_resp.json().get("fields", {}).get("attachment", [])
        print(f"Standard Attachments Found: {len(atts)}")
        for a in atts:
            print(f"  - {a.get('filename')}")


if __name__ == "__main__":
    debug()
