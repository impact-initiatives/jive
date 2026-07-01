import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_API_EMAIL")
JIRA_TOKEN = os.environ.get("JIRA_API_TOKEN")

if not JIRA_BASE_URL or not JIRA_EMAIL or not JIRA_TOKEN:
    print("[Error] Missing Jira environment variables in .env")
    sys.exit(1)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
HEADERS = {"Accept": "application/json", "X-ExperimentalApi": "opt-in"}


def verify_credentials():
    global AUTH, JIRA_BASE_URL
    print("--- [Step 0] Verifying Jira Credentials ---")
    if JIRA_TOKEN:
        print(
            f"  Token : Length={len(JIRA_TOKEN)} | Start={JIRA_TOKEN[:12]} | End={JIRA_TOKEN[-12:]}"
        )
    else:
        print("  Token : None")

    urls_to_try = [JIRA_BASE_URL, "https://reach-initiative.atlassian.net"]

    emails_to_try = [
        JIRA_EMAIL,
        "quentin.villotta@reach-initiative.org",
        "francesco.gizzarelli@impact-initiatives.org",
        "francesco.gizzarelli@reach-initiative.org",
    ]

    tokens_to_try = [JIRA_TOKEN]
    if JIRA_TOKEN and "=" in JIRA_TOKEN:
        tokens_to_try.append(JIRA_TOKEN.split("=")[0])

    for base_url in urls_to_try:
        if not base_url:
            continue
        print(f"\n  Testing base URL: {base_url}...")
        url = f"{base_url}/rest/api/3/myself"

        for token in tokens_to_try:
            print(f"    Testing token of length {len(token)}...")
            for email in emails_to_try:
                if not email:
                    continue
                print(f"      Attempting with email: {email}...")
                test_auth = HTTPBasicAuth(email, token)
                try:
                    resp = requests.get(url, auth=test_auth, headers=HEADERS, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()
                    print(f"      [Success] SUCCESSFULLY AUTHENTICATED with {email} on {base_url}!")
                    print(f"      User         : {data.get('displayName')}")
                    print(f"      Email        : {data.get('emailAddress')}")
                    print(f"      Active status: {data.get('active')}")
                    # Update globals
                    AUTH = test_auth
                    JIRA_BASE_URL = base_url
                    return True
                except Exception as e:
                    print(f"      Failed: {e}")

    return False


def list_recent_projects():
    print("--- [Step 1] Fetching active projects on your Jira site ---")
    url = f"{JIRA_BASE_URL}/rest/api/3/project"
    try:
        resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        projects = resp.json()
        print(f"Found {len(projects)} projects:")
        for p in projects[:15]:
            print(f"  - Key: {p.get('key')} | Name: {p.get('name')} | ID: {p.get('id')}")
        return [p.get("key") for p in projects]
    except Exception as e:
        print(f"  Failed to fetch projects: {e}")
        return []


def search_recent_issues():
    print("\n--- [Step 2] Searching recent issues on your Jira site ---")
    # Search for all issues, ordering by updated date
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    params = {
        "jql": "updated >= -30d order by updated desc",
        "maxResults": 10,
        "fields": "summary,project,attachment",
    }
    try:
        resp = requests.get(url, params=params, auth=AUTH, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        issues = resp.json().get("issues", [])
        print(f"Found {len(issues)} recent issues:")
        for issue in issues:
            attachments = issue.get("fields", {}).get("attachment", [])
            has_xlsx = any(
                a.get("filename", "").lower().endswith((".xlsx", ".xls")) for a in attachments
            )
            print(
                f"  - Key: {issue.get('key')} | Summary: {issue.get('fields', {}).get('summary')} |"
                f" Project: {issue.get('fields', {}).get('project', {}).get('key')} |"
                f" Has Excel Attachment: {has_xlsx}"
            )
        return issues
    except Exception as e:
        if "resp" in locals() and hasattr(resp, "text"):
            print(f"  Response Body: {resp.text}")
        print(f"  Failed to search issues: {e}")
        return []


def get_cloud_id():
    url = f"{JIRA_BASE_URL}/_edge/tenant_info"
    resp = requests.get(url, auth=AUTH, timeout=15)
    resp.raise_for_status()
    return resp.json()["cloudId"]


def get_issue_id(issue_key):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}?fields=id"
    resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("id")


def dump_proforma_forms(issue_key):
    print(f"\n--- [Step 3] Fetching ProForma Forms for issue {issue_key} ---")
    try:
        # Resolve cloud_id and issue_id
        cloud_id = get_cloud_id()
        issue_id = get_issue_id(issue_key)
        print(f"  Resolved Tenant Cloud ID: {cloud_id}")
        print(f"  Resolved Issue ID: {issue_id}")

        # 1. Query the modern Cloud Forms API
        url = f"https://api.atlassian.com/jira/forms/cloud/{cloud_id}/issue/{issue_id}/form"
        print(f"  Querying Cloud Forms API: {url}")
        resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=15)

        if resp.status_code in (200, 201):
            forms = resp.json()
            print(f"\n=== Found {len(forms)} Forms via Cloud Forms API ===")
            for idx, f in enumerate(forms):
                form_id = f.get("id")
                print(
                    f"\n  Form {idx + 1}: ID: {form_id} | Name: {f.get('name')} | Submitted:"
                    f" {f.get('submitted')} | State: {f.get('state', {}).get('status')}"
                )

                # Fetch detailed answers of this form
                form_detail_url = f"{url}/{form_id}"
                detail_resp = requests.get(form_detail_url, auth=AUTH, headers=HEADERS, timeout=15)
                if detail_resp.status_code == 200:
                    form = detail_resp.json()

                    # Save comprehensive structure to local file
                    out_path = Path(__file__).parent / f"proforma_{issue_key}.json"
                    out_path.write_text(
                        json.dumps(form, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                    print(f"  [Saved] Saved comprehensive ProForma structure to: {out_path.name}")

                    questions = form.get("design", {}).get("questions", {})
                    answers = form.get("state", {}).get("answers", {})

                    print(f"\n    Questions ({len(questions)}):")
                    for qid, q in questions.items():
                        label = q.get("label", "(No label)")
                        # Console safe label printing
                        label_safe = label.encode("ascii", errors="replace").decode("ascii")
                        qtype = q.get("type", "unknown")
                        ans = answers.get(qid, {})
                        print(f"      - ID [{qid}] | Type: {qtype} | Label: '{label_safe}'")
                        if ans:
                            print(f"          Answer Value: {json.dumps(ans, ensure_ascii=True)}")
                else:
                    print(f"    Failed to retrieve form details: {detail_resp.status_code}")
            return
        else:
            print(
                f"  Cloud Forms API returned {resp.status_code}. Falling back to properties API..."
            )

    except Exception as e:
        print(
            f"  Modern Cloud Forms API failed/unsupported: {e}. Falling back to properties API..."
        )

    # Fallback to legacy/direct properties endpoint
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/properties/proforma.forms"
    print(f"  Querying Properties API: {url}")
    try:
        resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            print(
                f"  No ProForma forms property ('proforma.forms') found on issue {issue_key} (404)."
            )
            return
        resp.raise_for_status()
        data = resp.json()
        value = data.get("value", {})

        print("\n=== Comprehensive ProForma Structure (Legacy) ===")
        print(json.dumps(value, indent=2, ensure_ascii=False))

        forms = value.get("forms", [])
        print(f"\nParsed {len(forms)} Forms:")
        for idx, form in enumerate(forms):
            print(
                f"  Form {idx + 1}: ID: {form.get('id')} | Name: {form.get('name')} | State:"
                f" {form.get('state', {}).get('status')}"
            )
            questions = form.get("design", {}).get("questions", {})
            answers = form.get("state", {}).get("answers", {})

            print(f"    Questions ({len(questions)}):")
            for qid, q in questions.items():
                label = q.get("label", "(No label)")
                qtype = q.get("type", "unknown")
                ans = answers.get(qid, {})
                print(f"      - ID [{qid}] | Type: {qtype} | Label: '{label}'")
                if ans:
                    print(f"          Answer Value: {json.dumps(ans, ensure_ascii=False)}")

    except Exception as e:
        print(f"  Failed to retrieve ProForma properties: {e}")


def search_jsm_requests():
    print("\n--- [Step 2.5] Searching Jira Service Management Customer Requests ---")
    url = f"{JIRA_BASE_URL}/rest/servicedeskapi/request"
    params = {"requestOwnership": "ALL_REQUESTS", "requestStatus": "ALL_REQUESTS", "limit": 10}
    try:
        resp = requests.get(url, params=params, auth=AUTH, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        requests_list = data.get("values", [])
        print(f"Found {len(requests_list)} customer requests:")
        for r in requests_list:
            print(
                f"  - Key: {r.get('issueKey')} | Summary: {r.get('summary')} | Status:"
                " {r.get('currentStatus', {}).get('status')}"
            )
        return requests_list
    except Exception as e:
        if "resp" in locals() and hasattr(resp, "text"):
            print(f"  Response Body: {resp.text}")
        print(f"  Failed to search JSM requests: {e}")
        return []


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dump_proforma_forms(sys.argv[1])
    else:
        if verify_credentials():
            list_recent_projects()
            issues = search_recent_issues()
            jsm_requests = search_jsm_requests()

            target_key = None

            # Prioritize GDT-prefixed JSM requests for the active dev-env testing
            gdt_requests = [r for r in jsm_requests if r.get("issueKey", "").startswith("GDT-")]
            if gdt_requests:
                target_key = gdt_requests[0]["issueKey"]
                print(f"\n[Target Selection] Auto-targeting JSM GDT dev issue: {target_key}")
            elif jsm_requests:
                target_key = jsm_requests[0]["issueKey"]
            elif issues:
                target_key = issues[0]["key"]

            if target_key:
                dump_proforma_forms(target_key)
            else:
                print(
                    "\nNo recent issues or JSM customer requests found to dump ProForma structure."
                )
        else:
            print("\nSkipping further exploration because credentials verification failed.")
