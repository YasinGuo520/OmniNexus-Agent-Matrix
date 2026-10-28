"""
OmniNexus AI - Standalone Self-Healing & Outside Judge Verification (examples/quickstart_verification.py)
Zero-setup verification script for evaluation and testing.
"""

import sys
import os

# Set root
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from core.base_worker import BaseAutonomousWorker
from database.models import init_db, get_db
from core.ceo_agent import CEOAgent

class DemoCommerceWorker(BaseAutonomousWorker):
    def __init__(self):
        super().__init__(worker_name="DemoWorker", max_retries=3, max_budget_tokens=10000)
        self.attempts = 0

    def mock_flaky_scrape(self, fail_times=2):
        self.attempts += 1
        self.record_token_usage(300)
        if self.attempts <= fail_times:
            return {
                "http_status": 200,
                "raw_html": "Access restricted: CAPTCHA required",
                "items": []
            }
        return {
            "http_status": 200,
            "raw_html": "Normal catalogue payload",
            "items": [{"sku": "SKU-9821", "price": 49.9}, {"sku": "SKU-9822", "price": 89.0}]
        }

    def judge_payload(self, scratchpad: dict) -> tuple[bool, str]:
        if "CAPTCHA" in scratchpad.get("raw_html", ""):
            return False, "Outside Judge Intercept: CAPTCHA block detected"
        items = scratchpad.get("items", [])
        if len(items) == 0:
            return False, "Outside Judge Intercept: Zero items returned (silent failure)"
        return True, f"Outside Judge PASS: {len(items)} valid items verified"

def main():
    print("=" * 70)
    print("🚀 OMNINEXUS AI Autonomous Pipeline Verification")
    print("=" * 70)
    init_db()

    # Test 1: Self-healing
    print("\n▶️ [Test 1]: Flakiness Self-Healing Loop (Recovers after 2 backoffs)")
    worker = DemoCommerceWorker()
    res = worker.run_with_loop(
        task_name="Fetch Catalog Metrics",
        execute_fn=worker.mock_flaky_scrape,
        judge_fn=worker.judge_payload,
        fail_times=2
    )
    print(f"Status: {res['status']} | Notes: {res['notes']}")
    assert res["status"] == "SUCCESS", "Test 1 must succeed after backoff"

    # Test 2: Dead-Letter Queue
    print("\n▶️ [Test 2]: Dead-Letter Queue (DLQ) Circuit Breaker")
    worker2 = DemoCommerceWorker()
    res2 = worker2.run_with_loop(
        task_name="Severe Block Task",
        execute_fn=worker.mock_flaky_scrape,
        judge_fn=worker.judge_payload,
        fail_times=10
    )
    print(f"Status: {res2['status']} | Message: {res2['msg']}")
    assert res2["status"] == "DEAD_LETTER", "Test 2 must trigger DLQ cutoff"

    print("\n" + "=" * 70)
    print("🎉 All OmniNexus Core Moats 100% Verified Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
