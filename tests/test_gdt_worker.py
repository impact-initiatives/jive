import sys
from pathlib import Path
from dotenv import load_dotenv
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from worker import process_message

class MockMessage:
    def __init__(self, content):
        self.content = content
        self.id = "mock-message-id"
        self.dequeue_count = 1

def run_test(issue_key="GDT-31"):
    print(f"--- Starting JIVE Local Integration Test for {issue_key} ---")
    payload_json = f'{{"issue_key": "{issue_key}", "project_key": "GDT", "dataset_type": "jmmi"}}'
    msg = MockMessage(payload_json)
    try:
        process_message(msg)
        print("\n--- Test Completed Successfully! ---")
    except Exception as e:
        print(f"\n--- Test Failed with Exception: {e} ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    target_key = sys.argv[1] if len(sys.argv) > 1 else "GDT-31"
    run_test(target_key)
