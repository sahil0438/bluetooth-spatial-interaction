"""
Context Detector for Phase 5 — Context Awareness Engine.

Evaluates the current user context every 2 seconds based on:
  - Spatial state (from Phase 3 state machine)
  - System time (work hours check)
  - Gesture history (last 10 events with timestamps)
  - State duration (how long spatial state has been held)

Priority order: AWAY → PRESENTATION → FOCUS → WORK

Exports:
  get_current_context()  → str  (context name)
  get_context_info()     → dict (full context info with duration, reason)
  record_gesture(event)  → None (feed gesture history)
  evaluate()             → str  (run one evaluation cycle, return context)
"""
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from .contexts import (
    WORK_MODE,
    AWAY_MODE,
    PRESENTATION_MODE,
    FOCUS_MODE,
    AWAY_ABSENT_THRESHOLD_SEC,
    AWAY_RSSI_THRESHOLD,
    AWAY_RSSI_DURATION_SEC,
    FOCUS_PRESENT_THRESHOLD_SEC,
    FOCUS_NO_GESTURE_THRESHOLD_SEC,
    PRESENTATION_ACTIVATION_WINDOW_SEC,
    WORK_HOURS_START,
    WORK_HOURS_END,
)

# Log file
ROOT_DIR = Path(__file__).parent.parent
CONTEXT_LOG = ROOT_DIR / "logs" / "context_events.jsonl"

# Maximum gesture history to keep
MAX_GESTURE_HISTORY = 10


class ContextDetector:
    """
    Determines the active user context from spatial state, time, and gesture history.
    """

    def __init__(self):
        # Current context state
        self._current_context = WORK_MODE
        self._context_reason = "Initial default"
        self._context_changed_at = time.time()

        # Presentation mode — manually activated flag
        self._presentation_active = False

        # Gesture history — deque of (gesture_name, timestamp_float) tuples
        self._gesture_history = deque(maxlen=MAX_GESTURE_HISTORY)
        self._last_gesture_time = 0.0

        # Spatial state tracking (cached from last evaluation)
        self._last_spatial_state = "ABSENT"
        self._spatial_state_entered_at = time.time()

        # RSSI below threshold tracking
        self._rssi_below_threshold_since = None

        # Ensure log dir
        CONTEXT_LOG.parent.mkdir(parents=True, exist_ok=True)

    def record_gesture(self, gesture_event: dict):
        """
        Feed a new gesture event into the detector's history.

        Parameters:
            gesture_event: dict with keys: gesture, confidence, timestamp
        """
        gesture = gesture_event.get("gesture", "")
        ts_str = gesture_event.get("timestamp", "")

        try:
            ts_float = datetime.fromisoformat(ts_str).timestamp()
        except (ValueError, TypeError):
            ts_float = time.time()

        self._gesture_history.append((gesture, ts_float))
        self._last_gesture_time = ts_float

        # Check for presentation mode activation/deactivation
        self._check_presentation_trigger(gesture, ts_float)

    def _check_presentation_trigger(self, gesture: str, ts: float):
        """
        Check if DOUBLE_APPROACH x2 within 10 seconds triggers presentation mode.
        Also check if DOUBLE_APPROACH in presentation mode exits it.
        """
        if gesture == "DOUBLE_APPROACH" and self._presentation_active:
            # Already in presentation mode — DOUBLE_APPROACH exits it
            self._presentation_active = False
            return

        if gesture != "DOUBLE_APPROACH":
            return

        # Count DOUBLE_APPROACH events within the activation window
        now = ts
        recent_da = [
            t for (g, t) in self._gesture_history
            if g == "DOUBLE_APPROACH" and (now - t) <= PRESENTATION_ACTIVATION_WINDOW_SEC
        ]

        if len(recent_da) >= 2 and not self._presentation_active:
            self._presentation_active = True

    def evaluate(self) -> str:
        """
        Run one context evaluation cycle.

        Reads spatial state from the Phase 3 state machine singleton,
        checks all context conditions in priority order, and returns
        the determined context name.

        Returns:
            Context name string
        """
        # Import here to avoid circular imports at module load time
        from gesture_engine.state_machine import get_current_state, get_last_state_change_time

        state_dict = get_current_state()
        spatial_state = state_dict.get("state", "ABSENT")
        filtered_rssi = state_dict.get("rssi")
        state_change_time = get_last_state_change_time()

        now = time.time()
        current_hour = datetime.now().hour

        # Spatial state duration — use the state machine's timestamp directly.
        # state_change_time is the epoch time when the spatial state last changed,
        # which is authoritative regardless of when the detector was created.
        spatial_duration = now - state_change_time if state_change_time > 0 else 0.0

        # Update cached spatial state (for internal tracking only)
        self._last_spatial_state = spatial_state

        # Track RSSI below threshold
        if filtered_rssi is not None and filtered_rssi < AWAY_RSSI_THRESHOLD:
            if self._rssi_below_threshold_since is None:
                self._rssi_below_threshold_since = now
        else:
            self._rssi_below_threshold_since = None

        rssi_below_duration = 0.0
        if self._rssi_below_threshold_since is not None:
            rssi_below_duration = now - self._rssi_below_threshold_since

        # Time since last gesture
        gesture_gap = now - self._last_gesture_time if self._last_gesture_time > 0 else float("inf")

        # ── Priority 1: AWAY_MODE ──
        away_by_absent = (spatial_state == "ABSENT" and spatial_duration > AWAY_ABSENT_THRESHOLD_SEC)
        away_by_rssi = (rssi_below_duration > AWAY_RSSI_DURATION_SEC)

        if away_by_absent or away_by_rssi:
            reason = (
                f"ABSENT for {spatial_duration:.0f}s" if away_by_absent
                else f"RSSI < {AWAY_RSSI_THRESHOLD} for {rssi_below_duration:.0f}s"
            )
            self._set_context(AWAY_MODE, reason)
            return self._current_context

        # ── Priority 2: PRESENTATION_MODE ──
        if self._presentation_active:
            # Presentation mode requires user to be present
            if spatial_state in ("PRESENT_STABLE", "APPROACHING", "RAPID_APPROACH"):
                self._set_context(PRESENTATION_MODE, "DOUBLE_APPROACH x2 within 10s")
                return self._current_context
            else:
                # User left during presentation — deactivate
                self._presentation_active = False

        # ── Priority 3: FOCUS_MODE ──
        focus_present = (
            spatial_state == "PRESENT_STABLE"
            and spatial_duration > FOCUS_PRESENT_THRESHOLD_SEC
        )
        focus_no_gestures = (gesture_gap > FOCUS_NO_GESTURE_THRESHOLD_SEC)

        if focus_present and focus_no_gestures:
            self._set_context(
                FOCUS_MODE,
                f"PRESENT_STABLE for {spatial_duration / 60:.1f}min, "
                f"no gestures for {gesture_gap / 60:.1f}min"
            )
            return self._current_context

        # ── Priority 4: WORK_MODE (default fallback) ──
        if spatial_state in ("PRESENT_STABLE", "APPROACHING", "RAPID_APPROACH"):
            if WORK_HOURS_START <= current_hour < WORK_HOURS_END:
                self._set_context(WORK_MODE, "User present during work hours")
            else:
                self._set_context(WORK_MODE, "User present (outside work hours)")
        else:
            # Not clearly absent (< 30s) and not present — still default to WORK
            self._set_context(WORK_MODE, "Default context (transitional state)")

        return self._current_context

    def _set_context(self, new_context: str, reason: str):
        """Update the current context, logging transitions."""
        if new_context != self._current_context:
            old_context = self._current_context
            self._current_context = new_context
            self._context_reason = reason
            self._context_changed_at = time.time()

            # Log the transition
            transition = {
                "from": old_context,
                "to": new_context,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            }
            self._log_transition(transition)
        else:
            # Same context — update reason silently
            self._context_reason = reason

    def _log_transition(self, transition: dict):
        """Write context transition to log file and terminal."""
        try:
            with open(CONTEXT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(transition) + "\n")
        except Exception as e:
            print(f"[ERROR] Failed to write context event: {e}")

        print(f"\n  [CONTEXT] {transition['from']} -> {transition['to']}"
              f" | Reason: {transition['reason']}")

    def get_current_context(self) -> str:
        """Returns the current context name string."""
        return self._current_context

    def get_context_info(self) -> dict:
        """Returns full context info including duration and reason."""
        now = time.time()
        duration = now - self._context_changed_at

        return {
            "context": self._current_context,
            "reason": self._context_reason,
            "duration_seconds": round(duration, 1),
            "changed_at": datetime.fromtimestamp(self._context_changed_at).isoformat(),
            "presentation_active": self._presentation_active,
            "gesture_history_count": len(self._gesture_history),
            "last_gesture_time": self._last_gesture_time,
        }


    def reset_to_work_mode(self, reason: str):
        """Force reset context to WORK_MODE (used for manual exits)."""
        self._presentation_active = False
        self._set_context(WORK_MODE, reason)


# ============================================================
#  Module-level singleton
# ============================================================

_detector = None


def _get_detector() -> ContextDetector:
    """Lazy-init and return the global detector singleton."""
    global _detector
    if _detector is None:
        _detector = ContextDetector()
    return _detector


def init_detector() -> ContextDetector:
    """Explicitly initialize the detector singleton."""
    global _detector
    _detector = ContextDetector()
    return _detector


def get_current_context() -> str:
    """Returns the current context name string."""
    return _get_detector().get_current_context()


def get_context_info() -> dict:
    """Returns full context info dict."""
    return _get_detector().get_context_info()


def record_gesture(gesture_event: dict):
    """Feed a gesture event into the detector."""
    _get_detector().record_gesture(gesture_event)


def reset_to_work_mode(reason: str):
    """Force reset context to WORK_MODE."""
    _get_detector().reset_to_work_mode(reason)


def evaluate() -> str:
    """Run one context evaluation cycle."""
    return _get_detector().evaluate()


if __name__ == "__main__":
    print("=" * 60)
    print("  Context Detector — Phase 5 Module Check")
    print("=" * 60)
    det = ContextDetector()
    print(f"  Initial context: {det.get_current_context()}")
    print(f"  Context info: {det.get_context_info()}")
    print("  Context detector module loaded successfully.")
