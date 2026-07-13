import asyncio
import json
from pathlib import Path


class TerminalVisualizer:
    """
    Tails logs/filtered_scan.jsonl and feeds filtered RSSI data to the scanner
    for unified display. Does NOT print anything to the terminal itself — all
    rendering is handled by the BleScanner's device table.
    """
    def __init__(self, filtered_log_path: Path):
        self.filtered_log_path = Path(filtered_log_path)
        self.latest_data = {
            "timestamp": "N/A",
            "raw_rssi": None,
            "filtered_rssi": None,
            "status": "waiting"
        }
        self.running = False
        self._scanner = None  # Reference to BleScanner for pushing data

    def set_scanner(self, scanner):
        """Set the scanner reference so we can push filtered data to its display."""
        self._scanner = scanner

    async def run(self):
        """Tails the filtered log and pushes data to the scanner."""
        self.running = True
        await self._tail_log()

    def stop(self):
        """Stops the visualizer."""
        self.running = False

    async def _tail_log(self):
        """Tails the filtered scan log file and updates the scanner's display data."""
        while self.running and not self.filtered_log_path.exists():
            await asyncio.sleep(0.5)

        if not self.running:
            return

        with open(self.filtered_log_path, "r", encoding="utf-8") as f:
            # Go to end to process only new entries
            f.seek(0, 2)
            while self.running:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.05)
                    continue

                try:
                    data = json.loads(line.strip())
                    self.latest_data = data

                    # Push filtered RSSI and status to the scanner for display
                    if self._scanner is not None:
                        filtered = data.get("filtered_rssi")
                        status = data.get("status", "waiting")
                        timestamp = data.get("timestamp")

                        if filtered is not None:
                            self._scanner.filtered_rssi = filtered
                        self._scanner.target_status = status

                        # Update state machine and push spatial metrics to scanner
                        from gesture_engine import state_machine
                        state_machine.update(filtered, timestamp, status)
                        state_dict = state_machine.get_current_state()

                        self._scanner.spatial_state = state_dict.get("state", "ABSENT")
                        self._scanner.spatial_confidence = state_dict.get("confidence", 100.0)
                        self._scanner.spatial_trend = state_dict.get("trend_direction", "STABLE")
                        self._scanner.spatial_slope = state_dict.get("slope", 0.0)
                        self._scanner.spatial_last_change = state_machine.get_last_state_change_time()

                        # Push latest gesture info to scanner
                        from gesture_engine.gesture_recogniser import get_latest_gesture
                        latest_gesture = get_latest_gesture()
                        if latest_gesture is not None:
                            self._scanner.last_gesture_name = latest_gesture.get("gesture")
                            self._scanner.last_gesture_confidence = latest_gesture.get("confidence", 0.0)
                            # Parse the timestamp
                            import time as _time
                            from datetime import datetime as _dt
                            try:
                                ts = latest_gesture.get("timestamp", "")
                                self._scanner.last_gesture_time = _dt.fromisoformat(ts).timestamp()
                            except Exception:
                                self._scanner.last_gesture_time = _time.time()

                        # Push context info to scanner (Phase 5)
                        try:
                            from context_engine.context_detector import get_context_info
                            from context_engine.session_tracker import get_session_summary
                            from context_engine.contexts import ACTION_SHORT_LABELS

                            ctx_info = get_context_info()
                            self._scanner.context_name = ctx_info.get("context", "WORK_MODE")
                            self._scanner.context_active_since = ctx_info.get("duration_seconds", 0.0)

                            summary = get_session_summary()
                            recent = summary.get("recent_actions", [])
                            if recent:
                                last = recent[-1]
                                self._scanner.last_action_name = last.get("action", "")
                                try:
                                    import time as _time2
                                    from datetime import datetime as _dt2
                                    self._scanner.last_action_time = _dt2.fromisoformat(
                                        last.get("timestamp", "")).timestamp()
                                except Exception:
                                    self._scanner.last_action_time = _time2.time()
                        except ImportError:
                            pass  # Context engine not yet initialized

                except (json.JSONDecodeError, KeyError):
                    continue


if __name__ == "__main__":
    log_file = Path("logs/filtered_scan.jsonl")
    visualizer = TerminalVisualizer(log_file)
    print("TerminalVisualizer loaded successfully.")
