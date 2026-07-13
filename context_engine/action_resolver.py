"""
Action Resolver for Phase 5 — Context Awareness Engine.

Pure mapping function: (gesture_event, current_context) → action_instruction dict.
No state. Logs every resolved action to logs/action_decisions.jsonl.
"""
import json
from datetime import datetime
from pathlib import Path

from .contexts import (
    GESTURE_ACTION_MAP,
    ACTION_SHORT_LABELS,
    WORK_MODE,
)

# Log file path
ROOT_DIR = Path(__file__).parent.parent
ACTION_LOG = ROOT_DIR / "logs" / "action_decisions.jsonl"


def resolve(gesture_event: dict, current_context: str) -> dict:
    """
    Resolve a gesture event into an action instruction for Phase 6.

    Parameters:
        gesture_event: dict with keys: gesture, confidence, timestamp, rssi_sequence
        current_context: one of WORK_MODE, AWAY_MODE, PRESENTATION_MODE, FOCUS_MODE

    Returns:
        Action instruction dict:
        {
            "action": "VOLUME_ADJUST",
            "context": "WORK_MODE",
            "gesture": "ROTATION",
            "params": {"direction": "up", "steps": 2},
            "timestamp": "...",
            "confidence": 94.3
        }
    """
    gesture = gesture_event.get("gesture", "")
    confidence = gesture_event.get("confidence", 0.0)
    timestamp = gesture_event.get("timestamp", datetime.now().isoformat())

    # Look up the mapping
    key = (current_context, gesture)
    mapping = GESTURE_ACTION_MAP.get(key)

    if mapping is None:
        # Unknown combination — default to NO_ACTION
        action_instruction = {
            "action": "NO_ACTION",
            "context": current_context,
            "gesture": gesture,
            "params": {"reason": f"unmapped: {current_context}+{gesture}"},
            "timestamp": timestamp,
            "confidence": confidence,
        }
    else:
        action_instruction = {
            "action": mapping["action"],
            "context": current_context,
            "gesture": gesture,
            "params": dict(mapping["params"]),  # copy to avoid mutation
            "timestamp": timestamp,
            "confidence": confidence,
        }

    # Log the decision
    _log_action(action_instruction)

    # Print to terminal
    _print_action(action_instruction)

    return action_instruction


def _log_action(action_instruction: dict):
    """Append the action decision to the log file."""
    try:
        ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(action_instruction) + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to write action decision: {e}")


def _print_action(action_instruction: dict):
    """Print the resolved action to terminal."""
    context = action_instruction["context"]
    gesture = action_instruction["gesture"]
    action = action_instruction["action"]
    confidence = action_instruction["confidence"]
    short = ACTION_SHORT_LABELS.get(action, action)

    print(f"  [{context}] {gesture} -> {action} (conf: {confidence:.1f}%)")


if __name__ == "__main__":
    # Quick self-test
    print("=" * 60)
    print("  Action Resolver — Phase 5 Self-Test")
    print("=" * 60)

    test_cases = [
        ({"gesture": "ROTATION", "confidence": 94.3, "timestamp": "2026-06-16T12:00:00"}, "WORK_MODE"),
        ({"gesture": "SLOW_DEPARTURE", "confidence": 87.5, "timestamp": "2026-06-16T12:01:00"}, "WORK_MODE"),
        ({"gesture": "DOUBLE_APPROACH", "confidence": 91.2, "timestamp": "2026-06-16T12:02:00"}, "AWAY_MODE"),
        ({"gesture": "ROTATION", "confidence": 88.5, "timestamp": "2026-06-16T12:03:00"}, "PRESENTATION_MODE"),
        ({"gesture": "SLOW_DEPARTURE", "confidence": 87.5, "timestamp": "2026-06-16T12:04:00"}, "FOCUS_MODE"),
    ]

    for event, ctx in test_cases:
        result = resolve(event, ctx)
        print(f"    -> {result['action']} | params: {result['params']}")
    print("\n  Action resolver ready.")
