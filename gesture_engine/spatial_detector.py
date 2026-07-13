import time
from datetime import datetime
from pathlib import Path
import numpy as np

def calculate_trend(rssi_window, times_window):
    """
    Fits a linear regression line using NumPy polyfit (degree 1).
    
    Parameters:
        rssi_window (list of float): Last 10 filtered RSSI values
        times_window (list of float): Timestamps of those RSSI values (seconds since epoch)
        
    Returns:
        slope (float): Rate of change in dBm/second (positive = approaching, negative = departing)
        trend_strength (float): R-squared value (0 to 1, how consistent the trend is)
        direction (str): "APPROACHING" / "DEPARTING" / "STABLE"
    """
    if len(rssi_window) < 3:
        return 0.0, 1.0, "STABLE"

    # Convert times_window to relative seconds from start of window
    t0 = times_window[0]
    x = np.array([t - t0 for t in times_window])
    y = np.array(rssi_window)

    # Perform linear regression: y = slope * x + intercept
    slope, intercept = np.polyfit(x, y, 1)

    # Calculate R-squared (coefficient of determination)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    
    if ss_tot > 0:
        r_squared = float(1.0 - (ss_res / ss_tot))
    else:
        r_squared = 1.0

    # Ensure r_squared is within [0, 1]
    r_squared = max(0.0, min(1.0, r_squared))

    # Determine direction based on slope thresholds
    # slope > +1.5 = approaching
    # slope < -1.5 = departing
    # between -1.5 and +1.5 = stable
    if slope > 1.5:
        direction = "APPROACHING"
    elif slope < -1.5:
        direction = "DEPARTING"
    else:
        direction = "STABLE"

    return slope, r_squared, direction


class SpatialDetector:
    """
    Detects spatial events based on a sliding window of filtered RSSI values.
    """
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.rssi_window = []
        self.times_window = []  # Timestamps as floats (seconds since epoch)

    def clear(self):
        """Resets the sliding windows."""
        self.rssi_window.clear()
        self.times_window.clear()

    def parse_timestamp(self, ts) -> float:
        """Parses various timestamp formats into Unix epoch float."""
        if isinstance(ts, (int, float)):
            return float(ts)
        try:
            return datetime.fromisoformat(ts).timestamp()
        except Exception:
            return time.time()

    def add_reading(self, rssi: float, timestamp):
        """Appends a new reading to the sliding window, pruning if it exceeds window_size."""
        if rssi is None:
            return
        
        t_val = self.parse_timestamp(timestamp)
        self.rssi_window.append(rssi)
        self.times_window.append(t_val)

        if len(self.rssi_window) > self.window_size:
            self.rssi_window.pop(0)
            self.times_window.pop(0)

    def detect_proposed_state(self, current_state_name: str, last_seen_time: float, device_status: str) -> dict:
        """
        Evaluates the window and returns a dictionary with the proposed state and confidence score.
        
        Returns:
            dict: { "state": str, "confidence": float, "slope": float, "trend_direction": str }
        """
        now = self.times_window[-1] if self.times_window else time.time()
        
        # Hard events for immediate ABSENT: phone lost, timeout (>10s quiet), or absolute out of range (-127 dBm)
        is_device_lost_status = (device_status == "device_lost")
        is_timeout = (last_seen_time is not None and (now - last_seen_time > 10.0))
        is_out_of_range = (len(self.rssi_window) > 0 and self.rssi_window[-1] == -127.0)

        if is_device_lost_status or is_timeout or is_out_of_range:
            return {
                "state": "ABSENT",
                "confidence": 100.0,
                "slope": 0.0,
                "trend_direction": "STABLE"
            }

        if len(self.rssi_window) < 3:
            # Not enough data for trend analysis yet
            return {
                "state": current_state_name,
                "confidence": 100.0,
                "slope": 0.0,
                "trend_direction": "STABLE"
            }

        # Calculate trend using numpy polyfit
        slope, trend_strength, trend_direction = calculate_trend(self.rssi_window, self.times_window)
        current_rssi = self.rssi_window[-1]

        # Startup/Recovery rule: If currently ABSENT and phone is detected above -100 dBm,
        # propose APPROACHING to allow transition out of ABSENT.
        if current_state_name == "ABSENT" and current_rssi > -100.0:
            return {
                "state": "APPROACHING",
                "confidence": 100.0,
                "slope": round(slope, 3),
                "trend_direction": trend_direction
            }

        # Rule 4: ABSENT below -100 dBm
        # If the phone RSSI drops below -100 dBm, it should be considered ABSENT.
        # However, if we are currently in PRESENT_STABLE, the state machine only allows transition to DEPARTING.
        # So if the trend is DEPARTING, we propose DEPARTING first so we don't skip the state machine's required path.
        if current_rssi <= -100.0:
            if not (current_state_name == "PRESENT_STABLE" and trend_direction == "DEPARTING"):
                return {
                    "state": "ABSENT",
                    "confidence": 100.0,
                    "slope": round(slope, 3),
                    "trend_direction": trend_direction
                }

        # Rule 5: RAPID_APPROACH (RSSI increases by more than 20 dBm within 2 seconds)
        # Check all pairs in the window
        n = len(self.rssi_window)
        for i in range(n):
            for j in range(i + 1, n):
                dt = self.times_window[j] - self.times_window[i]
                dy = self.rssi_window[j] - self.rssi_window[i]
                if dt <= 2.0 and dy >= 20.0:
                    return {
                        "state": "RAPID_APPROACH",
                        "confidence": 100.0,
                        "slope": dy / max(0.1, dt),
                        "trend_direction": "APPROACHING"
                    }



        # Rule 1: APPROACHING
        # Condition: slope > +1.5 dBm/s and current RSSI is above -80 dBm
        if trend_direction == "APPROACHING" and current_rssi > -80.0:
            confidence = float(trend_strength * 100.0)
            return {
                "state": "APPROACHING",
                "confidence": round(confidence, 2),
                "slope": round(slope, 3),
                "trend_direction": trend_direction
            }

        # Rule 2: DEPARTING
        # Condition: slope < -1.5 dBm/s
        # Note: The state machine handles checking if previously PRESENT_STABLE or RAPID_APPROACH
        if trend_direction == "DEPARTING":
            confidence = float(trend_strength * 100.0)
            return {
                "state": "DEPARTING",
                "confidence": round(confidence, 2),
                "slope": round(slope, 3),
                "trend_direction": trend_direction
            }

        # Rule 3: PRESENT_STABLE
        # Condition: trend is STABLE, RSSI is between -40 and -80, variation within ±5 dB over last 5 seconds
        # Find readings in the last 5 seconds
        t_latest = self.times_window[-1]
        rssi_5s = [r for r, t in zip(self.rssi_window, self.times_window) if t_latest - t <= 5.0]
        
        if len(rssi_5s) >= 2:
            variation = max(rssi_5s) - min(rssi_5s)
            is_stable_5s = (variation <= 10.0) # within ±5 dBm
        else:
            variation = 0.0
            is_stable_5s = True

        if trend_direction == "STABLE" and (-80.0 <= current_rssi <= -40.0) and is_stable_5s:
            confidence = float(max(0.0, min(100.0, (1.0 - (variation / 10.0)) * 100.0)))
            return {
                "state": "PRESENT_STABLE",
                "confidence": round(confidence, 2),
                "slope": round(slope, 3),
                "trend_direction": trend_direction
            }

        # If it's stable but doesn't meet the strict PRESENT_STABLE range/stability rules,
        # or if it's between -80 and -100 and stable, keep the current state
        # to prevent jumping to invalid states.
        return {
            "state": current_state_name,
            "confidence": 100.0,
            "slope": round(slope, 3),
            "trend_direction": trend_direction
        }
