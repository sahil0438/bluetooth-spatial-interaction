"""
Action Executor for Phase 6.

Master router: receives action dict from context pipeline, checks safety,
and routes to the correct specific executor.
"""
import json
from datetime import datetime
from pathlib import Path

from . import safety_guard
from . import volume_executor
from . import lock_executor
from . import wake_executor
from . import slide_executor
from . import dnd_executor

# Paths
ROOT_DIR = Path(__file__).parent.parent
ACTION_LOG = ROOT_DIR / "logs" / "action_log.jsonl"


def _log_execution(action_dict: dict, result: str = "SUCCESS", details: str = ""):
    """Log successful executions."""
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().timestamp(),
        "action": action_dict.get("action"),
        "result": result,
        "details": details,
        "gesture": action_dict.get("gesture"),
        "context": action_dict.get("context"),
        "params_used": action_dict.get("params")
    }
    
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to write execution log: {e}")


def _log_no_action(action_dict: dict):
    """Silently log NO_ACTION."""
    # We can just write to action_log but not print it
    _log_execution(action_dict)


def _log_unknown(action_dict: dict):
    """Log unknown action gracefully."""
    print(f"  [ERROR] Unknown action type routed: {action_dict.get('action')}")


def execute(action_dict: dict) -> bool:
    """
    Execute the given action dict.
    Runs safety checks first.
    Returns True if executed, False if blocked or failed.
    """
    # Print execution summary with timestamp
    ts = datetime.now().strftime("%H:%M:%S")
    action_name = action_dict.get('action', 'UNKNOWN')
    print(f"\n[{ts}] Processing: {action_name}")

    # Step 1: safety check
    safe, reason = safety_guard.is_safe_to_execute(action_dict)
    if not safe:
        # safety_guard already logged the block
        return False

    action = action_dict.get("action", "")
    params = action_dict.get("params", {})
    details = ""

    try:
        if action == "VOLUME_ADJUST":
            direction = params.get("direction", "up")
            steps = params.get("steps", 1)
            new_vol = volume_executor.adjust_volume(direction, steps)
            details = f"Volume {direction} by {steps} step(s) -> {int(new_vol * 100)}%"
        elif action == "LOCK_SCREEN":
            delay = params.get("delay_seconds", 0)
            lock_executor.lock_with_delay(delay)
            details = f"Lock screen (delay={delay}s)"
        elif action == "WAKE_SCREEN":
            show_summary = params.get("show_summary", False)
            wake_executor.wake(show_summary)
            details = "Screen woken" + (" + summary" if show_summary else "")
        elif action == "NEXT_SLIDE":
            slide_executor.next_slide()
            details = "Next slide key press"
        elif action == "PREV_SLIDE":
            slide_executor.prev_slide()
            details = "Prev slide key press"
        elif action == "TOGGLE_DND":
            dnd_executor.toggle()
            details = "Focus Assist toggled"
        elif action in ("EXIT_PRESENTATION", "EXIT_FOCUS"):
            lock_executor.exit_special_mode(action)
            details = f"Exited {action}"
        elif action == "NO_ACTION":
            _log_execution(action_dict, "SUCCESS", "No action needed")
            return True # NO_ACTION successfully processed by doing nothing
        else:
            _log_unknown(action_dict)
            return False
            
        # Log successful execution
        _log_execution(action_dict, "SUCCESS", details)
        return True
        
    except Exception as e:
        print(f"  [ERROR] Execution failed: {e}")
        _log_execution(action_dict, "FAILED", str(e))
        return False

