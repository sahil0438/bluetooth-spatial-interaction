import json
import time
import random
from pathlib import Path
from PyQt6.QtCore import QThread

class DemoModeRunner(QThread):
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.running = True
        
        # Ensure log folder exists
        (self.root_dir / "logs").mkdir(exist_ok=True)
        
        self.log_paths = {
            "filtered_scan": root_dir / "logs" / "filtered_scan.jsonl",
            "spatial_events": root_dir / "logs" / "spatial_events.jsonl",
            "gesture_events": root_dir / "logs" / "gesture_events.jsonl",
            "action_log": root_dir / "logs" / "action_log.jsonl",
            "safety_blocks": root_dir / "logs" / "safety_blocks.jsonl",
            "context_events": root_dir / "logs" / "context_events.jsonl",
            "session_summary": root_dir / "logs" / "session_summary.json",
        }

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        # Truncate all log files to start fresh
        for key, path in self.log_paths.items():
            if key == "session_summary":
                # Write empty JSON
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("")
        
        start_time = time.time()
        last_t = -1.0
        
        # Track statistics to generate live session_summary
        stats = {
            "work_mode_seconds": 0.0,
            "away_mode_seconds": 0.0,
            "focus_mode_seconds": 0.0,
            "presentation_mode_seconds": 0.0,
            "gestures": {"ROTATION": 0, "SLOW_DEPARTURE": 0, "DOUBLE_APPROACH": 0},
            "actions_taken": 0,
            "safety_blocks": 0,
            "current_volume": 50
        }
        
        current_ctx = "AWAY_MODE"
        ctx_change_time = start_time
        
        # Initial stats write
        self._write_summary(stats)

        while self.running:
            now = time.time()
            t = now - start_time
            
            # Restart loop at 90 seconds
            if t >= 90.0:
                start_time = now
                t = 0.0
                last_t = -1.0
                current_ctx = "AWAY_MODE"
                ctx_change_time = now
                # Reset counters
                stats = {
                    "work_mode_seconds": 0.0,
                    "away_mode_seconds": 0.0,
                    "focus_mode_seconds": 0.0,
                    "presentation_mode_seconds": 0.0,
                    "gestures": {"ROTATION": 0, "SLOW_DEPARTURE": 0, "DOUBLE_APPROACH": 0},
                    "actions_taken": 0,
                    "safety_blocks": 0,
                    "current_volume": 50
                }
                self._write_summary(stats)
                
            # Accumulate context times
            delta = now - ctx_change_time
            ctx_change_time = now
            if current_ctx == "WORK_MODE":
                stats["work_mode_seconds"] += delta
            elif current_ctx == "AWAY_MODE":
                stats["away_mode_seconds"] += delta
            elif current_ctx == "FOCUS_MODE":
                stats["focus_mode_seconds"] += delta
            elif current_ctx == "PRESENTATION_MODE":
                stats["presentation_mode_seconds"] += delta
                
            self._write_summary(stats)

            # 1. Update RSSI scan (every 500ms)
            if int(t * 2) != int(last_t * 2):
                # Calculate RSSI curve
                if t < 10.0:
                    # Rises -90 -> -45
                    rssi = -90.0 + (4.5 * t)
                elif t < 35.0:
                    # Stable around -48
                    rssi = -48.0
                elif t < 50.0:
                    # Stable around -50
                    rssi = -50.0
                elif t < 65.0:
                    # Stable around -52
                    rssi = -52.0
                elif t < 80.0:
                    # Stable around -47
                    rssi = -47.0
                else:
                    # Drops to -127
                    rssi = -47.0 - (8.0 * (t - 80.0))
                    rssi = max(-127.0, rssi)
                
                # Add noise
                rssi += random.uniform(-1.5, 1.5)
                raw_rssi = rssi + random.uniform(-3, 3)
                
                self._append_line("filtered_scan", {
                    "timestamp": now,
                    "raw_rssi": round(raw_rssi, 1),
                    "filtered_rssi": round(rssi, 1)
                })

            # 2. Trigger Event Sequence (relative timeline)
            events = [
                # t, event_type, data
                (2.0, "spatial", {"new_state": "APPROACHING", "confidence": 0.85}),
                (8.0, "spatial", {"new_state": "PRESENT_STABLE", "confidence": 0.95}),
                (8.1, "context", {"new_context": "WORK_MODE", "reason": "User present stable"}),
                
                # Volume Adjust 1
                (12.0, "gesture", {"gesture": "ROTATION", "confidence": 0.943}),
                (12.1, "action", {"action": "VOLUME_ADJUST", "result": "SUCCESS", "details": "Volume: 50% -> 60%", "vol": 60}),
                
                # Volume Adjust 2
                (22.0, "gesture", {"gesture": "ROTATION", "confidence": 0.910}),
                (22.1, "action", {"action": "VOLUME_ADJUST", "result": "SUCCESS", "details": "Volume: 60% -> 70%", "vol": 70}),
                
                # Safety Block (low confidence rotation)
                (26.0, "gesture", {"gesture": "ROTATION", "confidence": 0.450}),
                (26.1, "block", {"action": "VOLUME_ADJUST", "reason": "Confidence 45.0% below 70.0% threshold"}),
                
                # Volume Adjust 3
                (30.0, "gesture", {"gesture": "ROTATION", "confidence": 0.925}),
                (30.1, "action", {"action": "VOLUME_ADJUST", "result": "SUCCESS", "details": "Volume: 70% -> 80%", "vol": 80}),
                
                # Double Approach leading to Presentation Mode
                (38.0, "gesture", {"gesture": "DOUBLE_APPROACH", "confidence": 0.880}),
                (45.0, "gesture", {"gesture": "DOUBLE_APPROACH", "confidence": 0.915}),
                (45.1, "context", {"new_context": "PRESENTATION_MODE", "reason": "Double approach context switch"}),
                
                # Slide events
                (52.0, "gesture", {"gesture": "ROTATION", "confidence": 0.930}),
                (52.1, "action", {"action": "NEXT_SLIDE", "result": "SUCCESS", "details": "Next slide key press"}),
                
                (58.0, "spatial", {"new_state": "DEPARTING", "confidence": 0.75}),
                (58.1, "gesture", {"gesture": "SLOW_DEPARTURE", "confidence": 0.850}),
                (58.2, "action", {"action": "PREV_SLIDE", "result": "SUCCESS", "details": "Prev slide key press"}),
                (59.0, "spatial", {"new_state": "PRESENT_STABLE", "confidence": 0.90}),
                
                (63.0, "gesture", {"gesture": "DOUBLE_APPROACH", "confidence": 0.890}),
                (63.1, "context", {"new_context": "WORK_MODE", "reason": "Double approach context reset"}),
                
                # Focus Mode
                (72.0, "context", {"new_context": "FOCUS_MODE", "reason": "Extended stable session"}),
                
                # Departure & Lock
                (82.0, "spatial", {"new_state": "DEPARTING", "confidence": 0.80}),
                (82.1, "gesture", {"gesture": "SLOW_DEPARTURE", "confidence": 0.920}),
                (82.2, "action", {"action": "LOCK_SCREEN", "result": "SUCCESS", "details": "Lock screen triggered"}),
                
                (87.0, "spatial", {"new_state": "ABSENT", "confidence": 1.0}),
                (87.1, "context", {"new_context": "AWAY_MODE", "reason": "User absent"})
            ]

            for ev_t, ev_type, ev_data in events:
                if last_t < ev_t <= t:
                    # Trigger this event!
                    if ev_type == "spatial":
                        self._append_line("spatial_events", {
                            "timestamp": now,
                            "previous_state": "ABSENT" if ev_data["new_state"] == "APPROACHING" else "PRESENT_STABLE",
                            "new_state": ev_data["new_state"],
                            "confidence": ev_data["confidence"]
                        })
                    elif ev_type == "context":
                        current_ctx = ev_data["new_context"]
                        self._append_line("context_events", {
                            "timestamp": now,
                            "previous_context": "AWAY_MODE" if current_ctx == "WORK_MODE" else "WORK_MODE",
                            "new_context": current_ctx,
                            "reason": ev_data["reason"]
                        })
                    elif ev_type == "gesture":
                        gest = ev_data["gesture"]
                        stats["gestures"][gest] += 1
                        self._append_line("gesture_events", {
                            "timestamp": now,
                            "gesture": gest,
                            "confidence": ev_data["confidence"]
                        })
                    elif ev_type == "action":
                        stats["actions_taken"] += 1
                        if "vol" in ev_data:
                            stats["current_volume"] = ev_data["vol"]
                        self._append_line("action_log", {
                            "timestamp": now,
                            "action": ev_data["action"],
                            "result": ev_data["result"],
                            "details": ev_data["details"]
                        })
                    elif ev_type == "block":
                        stats["safety_blocks"] += 1
                        self._append_line("safety_blocks", {
                            "timestamp": now,
                            "action": ev_data["action"],
                            "reason": ev_data["reason"]
                        })

            last_t = t
            time.sleep(0.1)

    def _append_line(self, key, data):
        path = self.log_paths[key]
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            pass

    def _write_summary(self, stats):
        path = self.log_paths["session_summary"]
        
        # Format as requested in session statistics bar
        total_time = (
            stats["work_mode_seconds"] +
            stats["away_mode_seconds"] +
            stats["focus_mode_seconds"] +
            stats["presentation_mode_seconds"]
        )
        
        summary = {
            "total_duration": total_time,
            "context_durations": {
                "WORK_MODE": stats["work_mode_seconds"],
                "AWAY_MODE": stats["away_mode_seconds"],
                "FOCUS_MODE": stats["focus_mode_seconds"],
                "PRESENTATION_MODE": stats["presentation_mode_seconds"]
            },
            "gesture_counts": stats["gestures"],
            "total_actions": stats["actions_taken"],
            "total_safety_blocks": stats["safety_blocks"],
            "current_volume": stats["current_volume"]
        }
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            pass
