import sys

import requests

URL = "http://localhost:8000/api/webhook"

HEADERS = {"Content-Type": "application/json", "x-functions-key": "local-dev-key"}

payloads = {
    "dataset": {
        "issue_key": "RQA-123",
        "project_key": "RQA",
        "rcid": "UKR2401",
        "dataset_type": "jmmi",
    },
    "custom_secure_link": {
        "issue_key": "RQA-456",
        "project_key": "RQA",
        "rcid": "UKR2402",
        "dataset_type": "msna",
        "secure_link": "https://example.com/download/ Ukraine_JMMI_R40.xlsx",
    },
}


def send_test_webhook(name, data):
    print(f"\nSending test webhook: {name}...")
    try:
        resp = requests.post(URL, headers=HEADERS, json=data, timeout=10)
        print(f"  Status Code : {resp.status_code}")
        print(f"  Response    : {resp.text}")
    except requests.exceptions.ConnectionError:
        print(
            "  [Error] Failed to connect. Is the JIVE docker stack running? (docker compose up -d)"
        )


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "dataset"
    if choice not in payloads:
        print(f"Unknown payload. Choose from: {list(payloads.keys())}")
        sys.exit(1)
    send_test_webhook(choice, payloads[choice])
