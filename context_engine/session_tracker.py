"""
Session Tracker for Phase 5 — Context Awareness Engine.

Tracks cumulative session statistics:
  - Total time in each context
  - Gesture counts per session
  - Total actions taken
  - Last 5 actions with timestamps

Auto-saves to logs/session_summary.json every 5 minutes.

Exports:
  get_session_summary() → dict
"""
import asyncio
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from .contexts import CONTEXT_NAMES

# Paths
ROOT_DIR = Path(__file__).parent.parent
SESSION_FILE = ROOT_DIR / "logs" / "session_summary.json"

# Auto-save interval
AUTO_SAVE_INTERVAL_SEC = 300  # 5 minutes


class SessionTracker:
    """
    Tracks running session statistics for the Phase 7 dashboard.
    """

    def __init__(self):
        self.session_start = time.time()
        self.session_start_iso = datetime.now().isoformat()

        # Context duration tracking
        self._context_durations = {name: 0.0 for name in CONTEXT_NAMES}
        self._current_context = "WORK_MODE"
        self._context_entered_at = time.time()

        # Gesture counts
        self._gesture_counts = {}

        # Action tracking
        self._actions_taken = 0
        self._recent_actions = deque(maxlen=5)

        # Safety blocks and Volume
        self._safety_blocks = 0
        self._current_volume = 50

        # Running flag for auto-save loop
        self.running = False

        # Ensure log dir
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def update_context(self, new_context: str):
        """
        Called when the context changes. Accumulates time in the old context.
        """
        now = time.time()
        elapsed = now - self._context_entered_at

        if self._current_context in self._context_durations:
            self._context_durations[self._current_context] += elapsed

        self._current_context = new_context
        self._context_entered_at = now

    def record_gesture(self, gesture_name: str):
        """Increment gesture count for this session."""
        if gesture_name not in self._gesture_counts:
            self._gesture_counts[gesture_name] = 0
        self._gesture_counts[gesture_name] += 1

    def record_action(self, action_dict: dict):
        """Record an action taken."""
        self._actions_taken += 1
        self._recent_actions.append({
            "action": action_dict.get("action", "UNKNOWN"),
            "gesture": action_dict.get("gesture", ""),
            "context": action_dict.get("context", ""),
            "timestamp": action_dict.get("timestamp", datetime.now().isoformat()),
        })

    def record_safety_block(self):
        """Record a safety block event."""
        self._safety_blocks += 1

    def update_volume(self, volume: int):
        """Update tracked system volume."""
        self._current_volume = int(volume)

    def get_session_summary(self) -> dict:
        """
        Build and return the current session summary.
        """
        now = time.time()

        # Include time accumulated in the current context
        context_durations = dict(self._context_durations)
        current_elapsed = now - self._context_entered_at
        if self._current_context in context_durations:
            context_durations[self._current_context] += current_elapsed

        total_duration = now - self.session_start

        return {
            "total_duration": total_duration,
            "context_durations": context_durations,
            "gesture_counts": dict(self._gesture_counts),
            "total_actions": self._actions_taken,
            "total_safety_blocks": self._safety_blocks,
            "current_volume": self._current_volume,
            "session_start": self.session_start_iso,
            "recent_actions": list(self._recent_actions),
        }

    def save_summary(self):
        """Save the session summary to disk."""
        summary = self.get_session_summary()
        try:
            import builtins
            _open = getattr(builtins, 'open', None)
            if _open is None:
                return  # Interpreter shutting down, builtins cleared
            with _open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=4)
        except Exception as e:
            try:
                print(f"[ERROR] Failed to save session summary: {e}")
            except Exception:
                pass  # stdout may also be gone during shutdown

    async def auto_save_loop(self):
        """Background loop that saves session summary every 5 minutes."""
        self.running = True
        while self.running:
            await asyncio.sleep(AUTO_SAVE_INTERVAL_SEC)
            if self.running:
                self.save_summary()

    def stop(self):
        """Stop the auto-save loop and perform final save."""
        self.running = False
        self.save_summary()


# ============================================================
#  Module-level singleton
# ============================================================

_tracker = None


def _get_tracker() -> SessionTracker:
    """Lazy-init and return the global tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = SessionTracker()
    return _tracker


def init_tracker() -> SessionTracker:
    """Explicitly initialize the tracker singleton."""
    global _tracker
    _tracker = SessionTracker()
    return _tracker


def get_session_summary() -> dict:
    """Returns the current session summary dict."""
    return _get_tracker().get_session_summary()


def update_context(new_context: str):
    """Update context in session tracker."""
    _get_tracker().update_context(new_context)


def record_gesture(gesture_name: str):
    """Record a gesture in session stats."""
    _get_tracker().record_gesture(gesture_name)


def record_action(action_dict: dict):
    """Record an action in session stats."""
    _get_tracker().record_action(action_dict)


def record_safety_block():
    """Record a safety block in session stats."""
    _get_tracker().record_safety_block()


def update_volume(volume: int):
    """Update the current volume in session stats."""
    _get_tracker().update_volume(volume)


def save_summary():
    """Force-save the session summary."""
    _get_tracker().save_summary()


def stop():
    """Stop tracker and save final summary."""
    _get_tracker().stop()


if __name__ == "__main__":
    print("=" * 60)
    print("  Session Tracker — Phase 5 Module Check")
    print("=" * 60)
    tracker = SessionTracker()
    tracker.record_gesture("ROTATION")
    tracker.record_gesture("ROTATION")
    tracker.record_gesture("SLOW_DEPARTURE")
    tracker.record_action({"action": "VOLUME_ADJUST", "gesture": "ROTATION",
                           "context": "WORK_MODE", "timestamp": datetime.now().isoformat()})
    print(json.dumps(tracker.get_session_summary(), indent=2))
    print("  Session tracker module loaded successfully.")
