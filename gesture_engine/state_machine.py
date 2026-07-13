import json
import time
from datetime import datetime
from pathlib import Path
from .spatial_detector import SpatialDetector

# Enforce valid state transitions only
ALLOWED_TRANSITIONS = {
    "ABSENT": {"APPROACHING"},
    "APPROACHING": {"PRESENT_STABLE", "ABSENT"},
    "PRESENT_STABLE": {"DEPARTING", "RAPID_APPROACH"},
    "DEPARTING": {"ABSENT", "PRESENT_STABLE"},
    "RAPID_APPROACH": {"PRESENT_STABLE"}
}

class StateMachineManager:
    """
    Manages the current spatial state of the tracking system.
    Enforces transitions and minimum state hold durations.
    """
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.spatial_events_log = self.log_dir / "spatial_events.jsonl"
        self.spatial_detector = SpatialDetector()
        
        # Startup state
        self.current_state = {
            "state": "ABSENT",
            "confidence": 100.0,
            "rssi": None,
            "timestamp": datetime.now().isoformat(),
            "slope": 0.0,
            "trend_direction": "STABLE"
        }
        self.last_state_change_time = 0.0  # Allow first transition immediately
        self.last_seen_time = None
        
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _log_transition(self, old_state: str, new_state: str, reason: str):
        """Writes the transition to logs and prints to console."""
        log_entry = {
            "state": new_state,
            "confidence": self.current_state["confidence"],
            "rssi": self.current_state["rssi"],
            "timestamp": self.current_state["timestamp"]
        }
        try:
            with open(self.spatial_events_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"[ERROR] Failed to write spatial event: {e}")

        print(f"\n[{self.current_state['timestamp']}] STATE TRANSITION: {old_state} -> {new_state} | Reason: {reason}")

    def update(self, filtered_rssi: float, timestamp: str, device_status: str) -> dict:
        """
        Processes a new filtered reading. Updates state if valid and returns the new state if changed.
        """
        t_val = self.spatial_detector.parse_timestamp(timestamp)

        # Initialize last_state_change_time based on first parsed packet timestamp
        if self.last_state_change_time == 0.0:
            self.last_state_change_time = t_val - 2.0

        # Update last seen time if device is actively seen
        if filtered_rssi is not None and filtered_rssi != -127 and device_status != "device_lost":
            self.last_seen_time = t_val

        # Time-based forced transition: RAPID_APPROACH -> PRESENT_STABLE (after 2 seconds)
        if self.current_state["state"] == "RAPID_APPROACH" and (t_val - self.last_state_change_time >= 2.0):
            old_state = "RAPID_APPROACH"
            new_state = "PRESENT_STABLE"
            
            self.current_state = {
                "state": new_state,
                "confidence": 100.0,
                "rssi": filtered_rssi,
                "timestamp": timestamp,
                "slope": 0.0,
                "trend_direction": "STABLE"
            }
            self.last_state_change_time = t_val
            self._log_transition(old_state, new_state, "Timer expired (2s hold in RAPID_APPROACH)")
            return self.current_state

        # Update sliding window inside the detector
        if filtered_rssi is not None:
            self.spatial_detector.add_reading(filtered_rssi, timestamp)

        # Detect the proposed state based on the current window
        proposed = self.spatial_detector.detect_proposed_state(
            self.current_state["state"],
            self.last_seen_time,
            device_status
        )

        proposed_state = proposed["state"]
        proposed_conf = proposed["confidence"]
        proposed_slope = proposed.get("slope", 0.0)
        proposed_trend = proposed.get("trend_direction", "STABLE")

        # Update dynamic fields on current_state regardless of state transition
        self.current_state["rssi"] = filtered_rssi
        self.current_state["confidence"] = proposed_conf
        self.current_state["slope"] = proposed_slope
        self.current_state["trend_direction"] = proposed_trend

        if proposed_state != self.current_state["state"]:
            old_state = self.current_state["state"]
            
            # Verify transition validity
            is_valid = proposed_state in ALLOWED_TRANSITIONS.get(old_state, set())
            
            # Verify minimum 2-second hold time
            has_held_2s = (t_val - self.last_state_change_time >= 2.0)

            if is_valid and has_held_2s:
                # Perform transition
                self.current_state["state"] = proposed_state
                self.current_state["timestamp"] = timestamp
                self.last_state_change_time = t_val

                # Construct descriptive reason
                reason = f"Trend {proposed_trend} (slope: {proposed_slope:+.2f} dBm/s), RSSI: {filtered_rssi} dBm"
                if proposed_state == "ABSENT":
                    reason = f"Signal lost or very weak (RSSI: {filtered_rssi}, status: {device_status})"
                elif proposed_state == "RAPID_APPROACH":
                    reason = f"Sudden RSSI spike (slope: {proposed_slope:+.2f} dBm/s)"

                self._log_transition(old_state, proposed_state, reason)
                return self.current_state

        return None


# Global singletons to export state functions
_manager = None

def init_state_machine(log_dir: Path):
    global _manager
    _manager = StateMachineManager(log_dir)

def get_current_state() -> dict:
    global _manager
    if _manager is None:
        root_dir = Path(__file__).parent.parent
        init_state_machine(root_dir / "logs")
    return _manager.current_state

def get_last_state_change_time() -> float:
    global _manager
    if _manager is None:
        return 0.0
    return _manager.last_state_change_time

def update(filtered_rssi: float, timestamp: str, device_status: str) -> dict:
    global _manager
    if _manager is None:
        root_dir = Path(__file__).parent.parent
        init_state_machine(root_dir / "logs")
    return _manager.update(filtered_rssi, timestamp, device_status)
