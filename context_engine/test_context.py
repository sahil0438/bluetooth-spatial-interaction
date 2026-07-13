"""
Phase 5 Context Engine — Standalone Test Script.

Tests context detection and action resolution WITHOUT live Bluetooth.
Mocks spatial state and gesture events to verify correct behavior.

Usage:
    python -m context_engine.test_context
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


# ============================================================
#  Test Helpers — Mock the state machine before importing
# ============================================================

# We need to mock gesture_engine.state_machine BEFORE importing context_detector
# because context_detector imports it at evaluate() time.

_mock_state = {
    "state": "PRESENT_STABLE",
    "confidence": 100.0,
    "rssi": -58.0,
    "timestamp": datetime.now().isoformat(),
    "slope": 0.0,
    "trend_direction": "STABLE",
}
_mock_state_change_time = time.time()


def _mock_get_current_state():
    return dict(_mock_state)


def _mock_get_last_state_change_time():
    return _mock_state_change_time


def _mock_init_state_machine(log_dir):
    pass


# Patch gesture_engine.state_machine before any context_engine import
import types

mock_sm = types.ModuleType("gesture_engine.state_machine")
mock_sm.get_current_state = _mock_get_current_state
mock_sm.get_last_state_change_time = _mock_get_last_state_change_time
mock_sm.init_state_machine = _mock_init_state_machine

# Also ensure gesture_engine package exists in sys.modules
if "gesture_engine" not in sys.modules:
    mock_ge = types.ModuleType("gesture_engine")
    sys.modules["gesture_engine"] = mock_ge

sys.modules["gesture_engine.state_machine"] = mock_sm

# NOW import context engine modules
from context_engine.context_detector import ContextDetector
from context_engine.action_resolver import resolve
from context_engine.contexts import (
    WORK_MODE, AWAY_MODE, PRESENTATION_MODE, FOCUS_MODE,
)


# ============================================================
#  Test Infrastructure
# ============================================================

_pass_count = 0
_fail_count = 0


def assert_eq(actual, expected, msg=""):
    global _pass_count, _fail_count
    if actual == expected:
        _pass_count += 1
        return True
    else:
        _fail_count += 1
        print(f"    ASSERTION FAILED: {msg}")
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        return False


def set_mock_state(state: str, rssi: float = -58.0, duration_ago: float = 0.0):
    """Configure the mock spatial state."""
    global _mock_state, _mock_state_change_time
    _mock_state["state"] = state
    _mock_state["rssi"] = rssi
    _mock_state_change_time = time.time() - duration_ago


# ============================================================
#  Test Cases
# ============================================================

def test_1_work_mode_rotation():
    """
    Test 1 — Work mode rotation:
      Spatial state: PRESENT_STABLE, Time: 14:00, No special conditions
      Gesture: ROTATION (confidence 94.3%)
      Expected: WORK_MODE -> VOLUME_ADJUST
    """
    print("\n  Test 1: Work mode + ROTATION -> VOLUME_ADJUST")
    print("  " + "-" * 55)

    set_mock_state("PRESENT_STABLE", rssi=-58.0, duration_ago=60.0)

    detector = ContextDetector()
    context = detector.evaluate()

    # Should be WORK_MODE (present + work hours fallback)
    c1 = assert_eq(context, WORK_MODE, "Context should be WORK_MODE")

    # Resolve the gesture
    gesture_event = {
        "gesture": "ROTATION",
        "confidence": 94.3,
        "timestamp": datetime.now().isoformat(),
        "rssi_sequence": [-55.2, -70.1, -54.8, -56.3, -72.0, -53.5, -55.1, -57.4],
    }
    action = resolve(gesture_event, context)

    c2 = assert_eq(action["action"], "VOLUME_ADJUST", "Action should be VOLUME_ADJUST")
    c3 = assert_eq(action["context"], WORK_MODE, "Context in action should be WORK_MODE")
    c4 = assert_eq(action["params"]["direction"], "up", "Direction should be 'up'")

    passed = c1 and c2 and c3 and c4
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_2_away_mode_approach():
    """
    Test 2 — Away mode approach:
      Spatial state: ABSENT (35 seconds), Time: 14:05
      Gesture: DOUBLE_APPROACH (confidence 91.2%)
      Expected: AWAY_MODE -> WAKE_SCREEN
    """
    print("\n  Test 2: Away mode + DOUBLE_APPROACH -> WAKE_SCREEN")
    print("  " + "-" * 55)

    # ABSENT for 35 seconds (> 30s threshold)
    set_mock_state("ABSENT", rssi=-105.0, duration_ago=35.0)

    detector = ContextDetector()
    context = detector.evaluate()

    c1 = assert_eq(context, AWAY_MODE, "Context should be AWAY_MODE")

    gesture_event = {
        "gesture": "DOUBLE_APPROACH",
        "confidence": 91.2,
        "timestamp": datetime.now().isoformat(),
        "rssi_sequence": [-85.0, -75.3, -76.1, -72.5, -66.8, -78.2, -67.0, -55.5],
    }
    action = resolve(gesture_event, context)

    c2 = assert_eq(action["action"], "WAKE_SCREEN", "Action should be WAKE_SCREEN")
    c3 = assert_eq(action["params"]["show_summary"], False, "show_summary should be False in AWAY_MODE")

    passed = c1 and c2 and c3
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_3_presentation_activation():
    """
    Test 3 — Presentation mode activation:
      Spatial state: PRESENT_STABLE, Time: 10:00
      Gesture sequence: DOUBLE_APPROACH, DOUBLE_APPROACH (within 10s)
      Expected: Context switches to PRESENTATION_MODE
    """
    print("\n  Test 3: DOUBLE_APPROACH x2 -> PRESENTATION_MODE activation")
    print("  " + "-" * 55)

    set_mock_state("PRESENT_STABLE", rssi=-55.0, duration_ago=120.0)

    detector = ContextDetector()

    # First DOUBLE_APPROACH
    now = datetime.now()
    event1 = {
        "gesture": "DOUBLE_APPROACH",
        "confidence": 91.2,
        "timestamp": now.isoformat(),
    }
    detector.record_gesture(event1)
    context1 = detector.evaluate()

    # Should still be WORK_MODE (only 1 DOUBLE_APPROACH so far)
    c1 = assert_eq(context1, WORK_MODE, "After 1st DOUBLE_APPROACH: still WORK_MODE")

    # Second DOUBLE_APPROACH within 10 seconds
    event2 = {
        "gesture": "DOUBLE_APPROACH",
        "confidence": 89.0,
        "timestamp": (now + timedelta(seconds=3)).isoformat(),
    }
    detector.record_gesture(event2)
    context2 = detector.evaluate()

    c2 = assert_eq(context2, PRESENTATION_MODE, "After 2nd DOUBLE_APPROACH: PRESENTATION_MODE")
    c3 = assert_eq(detector._presentation_active, True, "Presentation flag should be True")

    passed = c1 and c2 and c3
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_4_presentation_slide_control():
    """
    Test 4 — Presentation slide control:
      Context: PRESENTATION_MODE (already active)
      Gesture: ROTATION (confidence 88.5%)
      Expected: PRESENTATION_MODE -> NEXT_SLIDE
    """
    print("\n  Test 4: PRESENTATION_MODE + ROTATION -> NEXT_SLIDE")
    print("  " + "-" * 55)

    # We need a detector that's already in presentation mode
    set_mock_state("PRESENT_STABLE", rssi=-55.0, duration_ago=120.0)

    detector = ContextDetector()
    detector._presentation_active = True  # Manually activate

    context = detector.evaluate()
    c1 = assert_eq(context, PRESENTATION_MODE, "Context should be PRESENTATION_MODE")

    gesture_event = {
        "gesture": "ROTATION",
        "confidence": 88.5,
        "timestamp": datetime.now().isoformat(),
        "rssi_sequence": [-55.0, -70.0, -54.0, -56.0, -72.0, -53.0, -55.0, -57.0],
    }
    action = resolve(gesture_event, context)

    c2 = assert_eq(action["action"], "NEXT_SLIDE", "Action should be NEXT_SLIDE")
    c3 = assert_eq(action["context"], PRESENTATION_MODE, "Context in action should be PRESENTATION_MODE")

    passed = c1 and c2 and c3
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_5_focus_mode_departure():
    """
    Test 5 — Focus mode departure:
      Spatial state: PRESENT_STABLE for 12 minutes, no gestures for 6 minutes
      Gesture: SLOW_DEPARTURE (confidence 87.5%)
      Expected: FOCUS_MODE -> LOCK_SCREEN (delay 0s)
    """
    print("\n  Test 5: FOCUS_MODE + SLOW_DEPARTURE -> LOCK_SCREEN (delay=0)")
    print("  " + "-" * 55)

    # PRESENT_STABLE for 12 minutes (720 seconds > 600s threshold)
    set_mock_state("PRESENT_STABLE", rssi=-57.0, duration_ago=720.0)

    detector = ContextDetector()
    # Last gesture was 6 minutes ago (360 seconds > 300s threshold)
    detector._last_gesture_time = time.time() - 360.0

    context = detector.evaluate()
    c1 = assert_eq(context, FOCUS_MODE, "Context should be FOCUS_MODE")

    gesture_event = {
        "gesture": "SLOW_DEPARTURE",
        "confidence": 87.5,
        "timestamp": datetime.now().isoformat(),
        "rssi_sequence": [-48.0, -54.3, -60.1, -67.2, -73.5, -80.0, -87.3, -95.1],
    }
    action = resolve(gesture_event, context)

    c2 = assert_eq(action["action"], "LOCK_SCREEN", "Action should be LOCK_SCREEN")
    c3 = assert_eq(action["params"]["delay_seconds"], 0, "delay_seconds should be 0 in FOCUS_MODE")

    passed = c1 and c2 and c3
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


# ============================================================
#  Main
# ============================================================

def main():
    global _pass_count, _fail_count

    print("=" * 65)
    print("     CONTEXT ENGINE TEST SUITE — Phase 5")
    print("     Standalone (no Bluetooth required)")
    print("=" * 65)

    results = []
    results.append(("Test 1: Work mode rotation",        test_1_work_mode_rotation()))
    results.append(("Test 2: Away mode approach",         test_2_away_mode_approach()))
    results.append(("Test 3: Presentation activation",    test_3_presentation_activation()))
    results.append(("Test 4: Presentation slide control", test_4_presentation_slide_control()))
    results.append(("Test 5: Focus mode departure",       test_5_focus_mode_departure()))

    print("\n" + "=" * 65)
    print("  RESULTS SUMMARY")
    print("=" * 65)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"    {name:42s}  [{status}]")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    failed_count = total - passed_count

    print(f"\n  Total: {total} | Passed: {passed_count} | Failed: {failed_count}")
    print(f"  Assertions: {_pass_count} passed, {_fail_count} failed")

    if failed_count == 0:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {failed_count} TEST(S) FAILED!")

    print("=" * 65)

    return failed_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
