"""
Safety Guard for Phase 6 — Action Execution Layer.

Ensures all actions are safe to execute before passing them to the OS.
Checks:
1. Confidence >= 70%
2. Cooldown >= 1.5s since last action
3. Action is known
4. Specific checks (e.g., LOCK_SCREEN RSSI check)
"""
import json
import time
from datetime import datetime
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).parent.parent
SAFETY_LOG = ROOT_DIR / "logs" / "safety_blocks.jsonl"

# Constants
MIN_CONFIDENCE = 70.0
MIN_COOLDOWN_SEC = 1.5

# State
_last_execution_time = 0.0
_safety_block_count = 0

APPROVED_ACTIONS = {
    "VOLUME_ADJUST", "LOCK_SCREEN", "WAKE_SCREEN", "NEXT_SLIDE",
    "PREV_SLIDE", "TOGGLE_DND", "EXIT_PRESENTATION", "EXIT_FOCUS", "NO_ACTION"
}


def _log_block(action_dict: dict, reason: str, reason_code: str):
    """Log blocked actions to disk and print warning."""
    global _safety_block_count
    _safety_block_count += 1
    
    SAFETY_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "timestamp": time.time(),
        "action": action_dict.get("action", "UNKNOWN"),
        "reason_code": reason_code,
        "reason": reason,
        "gesture": action_dict.get("gesture"),
        "context": action_dict.get("context"),
        "confidence": action_dict.get("confidence")
    }
    
    try:
        with open(SAFETY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to write safety log: {e}")

    # Use yellow color for safety blocks
    action = action_dict.get("action", "UNKNOWN")
    print(f"\033[93m  [SAFETY] {action} blocked — {reason}\033[0m")


def is_safe_to_execute(action_dict: dict) -> tuple[bool, str]:
    """
    Check if an action is safe to execute.
    
    Returns:
        (is_safe: bool, reason: str)
    """
    global _last_execution_time
    
    action = action_dict.get("action", "")
    
    # 0. Fast-pass NO_ACTION (doesn't need safety checks, just skips execution)
    if action == "NO_ACTION":
        return True, "NO_ACTION allowed"

    # 1. Action known check
    if action not in APPROVED_ACTIONS:
        _log_block(action_dict, f"Action '{action}' not in approved list", "UNKNOWN_ACTION")
        return False, "UNKNOWN_ACTION"

    # 2. Confidence check
    confidence = action_dict.get("confidence", 0.0)
    if confidence < MIN_CONFIDENCE:
        _log_block(action_dict, f"Confidence {confidence:.1f}% below {MIN_CONFIDENCE}%", "LOW_CONFIDENCE_BLOCK")
        return False, "LOW_CONFIDENCE_BLOCK"

    # 3. Cooldown check
    now = time.time()
    elapsed = now - _last_execution_time
    if elapsed < MIN_COOLDOWN_SEC:
        _log_block(action_dict, f"cooldown active ({MIN_COOLDOWN_SEC - elapsed:.1f}s remaining)", "COOLDOWN_BLOCK")
        return False, "COOLDOWN_BLOCK"

    # 4. LOCK_SCREEN specific RSSI check
    if action == "LOCK_SCREEN":
        # Get latest state to check RSSI
        try:
            from gesture_engine.state_machine import get_current_state
            state = get_current_state()
            rssi = state.get("rssi")
            if rssi is not None and rssi >= -60.0:
                print(f"\033[93m  [SAFETY] LOCK_SCREEN warning — RSSI is strong ({rssi}). Adding extra 2s delay.\033[0m")
                # We allow it, but modify the delay in the action dict
                delay = action_dict.get("params", {}).get("delay_seconds", 0)
                if delay < 2:
                    action_dict.setdefault("params", {})["delay_seconds"] = delay + 2
        except ImportError:
            pass # Testing mode or state machine not ready

    # Safe! Update execution time
    _last_execution_time = now
    return True, "SAFE"


def get_block_count() -> int:
    return _safety_block_count
