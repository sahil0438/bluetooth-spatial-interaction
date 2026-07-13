"""
Context Definitions for Phase 5 — Context Awareness Engine.

Defines the 4 user contexts and the complete gesture → action mapping table.
This module is pure data — no I/O, no state, no side effects.
"""
from dataclasses import dataclass, field


# ============================================================
#  Context Names (constants used everywhere)
# ============================================================

WORK_MODE = "WORK_MODE"
AWAY_MODE = "AWAY_MODE"
PRESENTATION_MODE = "PRESENTATION_MODE"
FOCUS_MODE = "FOCUS_MODE"

CONTEXT_NAMES = [WORK_MODE, AWAY_MODE, PRESENTATION_MODE, FOCUS_MODE]


# ============================================================
#  Context Dataclass
# ============================================================

@dataclass(frozen=True)
class ContextDefinition:
    """Immutable definition of a user context."""
    name: str
    priority: int          # Lower = higher priority (1 = checked first)
    description: str
    gesture_actions: dict  # gesture_name → action_name mapping

    def get_action(self, gesture: str) -> str:
        """Return the action name for a gesture in this context."""
        return self.gesture_actions.get(gesture, "NO_ACTION")


# ============================================================
#  Context Definitions
# ============================================================

CONTEXT_WORK = ContextDefinition(
    name=WORK_MODE,
    priority=4,
    description="User is at desk working normally",
    gesture_actions={
        "ROTATION":        "VOLUME_ADJUST",
        "SLOW_DEPARTURE":  "LOCK_SCREEN",
        "DOUBLE_APPROACH": "WAKE_SCREEN",
    }
)

CONTEXT_AWAY = ContextDefinition(
    name=AWAY_MODE,
    priority=1,
    description="User has left the desk area",
    gesture_actions={
        "ROTATION":        "NO_ACTION",
        "SLOW_DEPARTURE":  "NO_ACTION",
        "DOUBLE_APPROACH": "WAKE_SCREEN",
    }
)

CONTEXT_PRESENTATION = ContextDefinition(
    name=PRESENTATION_MODE,
    priority=2,
    description="User is presenting slides or showing something on screen",
    gesture_actions={
        "ROTATION":        "NEXT_SLIDE",
        "SLOW_DEPARTURE":  "PREV_SLIDE",
        "DOUBLE_APPROACH": "EXIT_PRESENTATION",
    }
)

CONTEXT_FOCUS = ContextDefinition(
    name=FOCUS_MODE,
    priority=3,
    description="User is in deep work, do not disturb",
    gesture_actions={
        "ROTATION":        "TOGGLE_DND",
        "SLOW_DEPARTURE":  "LOCK_SCREEN",
        "DOUBLE_APPROACH": "EXIT_FOCUS",
    }
)

# Quick lookup by name
CONTEXTS = {
    WORK_MODE:         CONTEXT_WORK,
    AWAY_MODE:         CONTEXT_AWAY,
    PRESENTATION_MODE: CONTEXT_PRESENTATION,
    FOCUS_MODE:        CONTEXT_FOCUS,
}


# ============================================================
#  Gesture → Action Parameter Map
# ============================================================
#  Full 12-entry lookup: (context, gesture) → action dict with params.
#  The action_resolver uses this to build the final action instruction.
# ============================================================

GESTURE_ACTION_MAP = {
    # WORK_MODE
    (WORK_MODE, "ROTATION"):        {"action": "VOLUME_ADJUST",    "params": {"direction": "up", "steps": 2}},
    (WORK_MODE, "SLOW_DEPARTURE"):  {"action": "LOCK_SCREEN",      "params": {"delay_seconds": 3}},
    (WORK_MODE, "DOUBLE_APPROACH"): {"action": "WAKE_SCREEN",      "params": {"show_summary": True}},

    # AWAY_MODE
    (AWAY_MODE, "ROTATION"):        {"action": "NO_ACTION",        "params": {"reason": "user away"}},
    (AWAY_MODE, "SLOW_DEPARTURE"):  {"action": "NO_ACTION",        "params": {"reason": "already away"}},
    (AWAY_MODE, "DOUBLE_APPROACH"): {"action": "WAKE_SCREEN",      "params": {"show_summary": False}},

    # PRESENTATION_MODE
    (PRESENTATION_MODE, "ROTATION"):        {"action": "NEXT_SLIDE",       "params": {}},
    (PRESENTATION_MODE, "SLOW_DEPARTURE"):  {"action": "PREV_SLIDE",       "params": {}},
    (PRESENTATION_MODE, "DOUBLE_APPROACH"): {"action": "EXIT_PRESENTATION", "params": {}},

    # FOCUS_MODE
    (FOCUS_MODE, "ROTATION"):        {"action": "TOGGLE_DND",      "params": {}},
    (FOCUS_MODE, "SLOW_DEPARTURE"):  {"action": "LOCK_SCREEN",     "params": {"delay_seconds": 0}},
    (FOCUS_MODE, "DOUBLE_APPROACH"): {"action": "EXIT_FOCUS",      "params": {}},
}


# ============================================================
#  Action Short Labels (for terminal display)
# ============================================================

ACTION_SHORT_LABELS = {
    "VOLUME_ADJUST":    "VOL+",
    "LOCK_SCREEN":      "LOCK",
    "WAKE_SCREEN":      "WAKE",
    "NEXT_SLIDE":       "NEXT",
    "PREV_SLIDE":       "PREV",
    "EXIT_PRESENTATION": "EXIT-PRES",
    "TOGGLE_DND":       "DND",
    "EXIT_FOCUS":       "EXIT-FOCUS",
    "NO_ACTION":        "---",
}


# ============================================================
#  Timing Constants (used by context_detector)
# ============================================================

# AWAY_MODE: ABSENT for this many seconds triggers away
AWAY_ABSENT_THRESHOLD_SEC = 30.0
# AWAY_MODE: RSSI below this for extended time
AWAY_RSSI_THRESHOLD = -100.0
AWAY_RSSI_DURATION_SEC = 20.0

# FOCUS_MODE: PRESENT_STABLE for this many seconds
FOCUS_PRESENT_THRESHOLD_SEC = 600.0   # 10 minutes
# FOCUS_MODE: No gestures for this many seconds
FOCUS_NO_GESTURE_THRESHOLD_SEC = 300.0  # 5 minutes

# PRESENTATION_MODE: DOUBLE_APPROACH x2 within this window
PRESENTATION_ACTIVATION_WINDOW_SEC = 10.0

# WORK_MODE: Active hours
WORK_HOURS_START = 8   # 08:00
WORK_HOURS_END = 22    # 22:00


if __name__ == "__main__":
    print("=" * 60)
    print("  Context Definitions — Phase 5")
    print("=" * 60)
    for ctx in CONTEXTS.values():
        print(f"\n  {ctx.name} (priority {ctx.priority})")
        print(f"    {ctx.description}")
        for gesture, action in ctx.gesture_actions.items():
            print(f"    {gesture:20s} -> {action}")
    print(f"\n  Total mapping entries: {len(GESTURE_ACTION_MAP)}")
