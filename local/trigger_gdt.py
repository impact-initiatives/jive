import requests

URL = "http://localhost:8000/api/webhook"
HEADERS = {"Content-Type": "application/json", "x-functions-key": "local-dev-key"}
payload = {
    "issue_key": "GDT-32",
    "project_key": "GDT",
    "rcid": "CHE2602",
    "dataset_type": "testmodel",
    "secure_link": "https://repository.impact-initiatives.org/resources/view-resource/?id=75856",
    "force_revalidation": True,
}

try:
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=10)
    print(f"Status Code : {resp.status_code}")
    print(f"Response    : {resp.text}")
except requests.exceptions.ConnectionError:
    print("[Error] Failed to connect. Is the JIVE docker stack running? (docker compose up -d)")
