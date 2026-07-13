"""
Phase 6 Automation Layer — Standalone Test Script.

Tests all executors without live Bluetooth.
Simulates action dicts coming from the Phase 5 pipeline.

Usage:
    python -m automation.test_automation [--skip-lock]
"""
import sys
import time
import argparse
from datetime import datetime

from automation.action_executor import execute
from automation import safety_guard

def create_mock_dict(action: str, params: dict, conf: float = 95.0) -> dict:
    return {
        "action": action,
        "params": params,
        "confidence": conf,
        "gesture": "MOCK_GESTURE",
        "context": "MOCK_CONTEXT",
        "timestamp": datetime.now().isoformat()
    }

def run_tests(skip_lock: bool):
    print("=" * 65)
    print("     AUTOMATION LAYER TEST SUITE — Phase 6")
    print("     Standalone (no Bluetooth required)")
    print("=" * 65)

    # Need to manipulate the safety guard cooldown to run fast tests
    safety_guard.MIN_COOLDOWN_SEC = 0.0

    print("\n--- Test 1: Volume up ---")
    d1 = create_mock_dict("VOLUME_ADJUST", {"direction": "up", "steps": 2}, 94.3)
    execute(d1)
    
    print("\n--- Test 2: Volume down ---")
    d2 = create_mock_dict("VOLUME_ADJUST", {"direction": "down", "steps": 2}, 94.3)
    execute(d2)

    print("\n--- Test 3: Screen wake ---")
    d3 = create_mock_dict("WAKE_SCREEN", {"show_summary": False}, 91.2)
    execute(d3)

    print("\n--- Test 4: Safety block (low confidence) ---")
    d4 = create_mock_dict("LOCK_SCREEN", {"delay_seconds": 3}, 45.0)
    execute(d4)

    print("\n--- Test 5: Lock screen with countdown ---")
    if skip_lock:
        print("  SKIPPED due to --skip-lock flag")
    else:
        d5 = create_mock_dict("LOCK_SCREEN", {"delay_seconds": 3}, 87.5)
        execute(d5)

    print("\n--- Test 6: Slide navigation ---")
    d6a = create_mock_dict("NEXT_SLIDE", {}, 90.0)
    execute(d6a)
    d6b = create_mock_dict("PREV_SLIDE", {}, 90.0)
    execute(d6b)

    print("\n--- Test 7: NO_ACTION handling ---")
    d7 = create_mock_dict("NO_ACTION", {"reason": "user away"}, 100.0)
    execute(d7)

    print("\n" + "=" * 65)
    print("  TESTS COMPLETED. Check output above for errors.")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-lock", action="store_true", help="Skip the actual screen lock test")
    args = parser.parse_args()
    
    run_tests(args.skip_lock)
