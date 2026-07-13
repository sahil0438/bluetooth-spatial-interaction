import sys
import json
import time
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

class LogReader(QThread):
    # Signals
    rssi_updated = pyqtSignal(float, float, float)  # raw, filtered, timestamp
    spatial_state_changed = pyqtSignal(str, float, float)  # state, confidence, timestamp
    gesture_detected = pyqtSignal(str, float, float)  # gesture, confidence, timestamp
    action_executed = pyqtSignal(str, str, str, float)  # action, result, details, timestamp
    context_changed = pyqtSignal(str, str, float)  # context, reason, timestamp
    session_updated = pyqtSignal(dict)  # session statistics summary
    devices_updated = pyqtSignal(list)  # list of dicts: [{name, address, rssi, last_seen}, ...]
    
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.running = True
        
        # Log paths
        self.log_paths = {
            "filtered_scan": root_dir / "logs" / "filtered_scan.jsonl",
            "spatial_events": root_dir / "logs" / "spatial_events.jsonl",
            "gesture_events": root_dir / "logs" / "gesture_events.jsonl",
            "action_log": root_dir / "logs" / "action_log.jsonl",
            "safety_blocks": root_dir / "logs" / "safety_blocks.jsonl",
            "context_events": root_dir / "logs" / "context_events.jsonl",
            "session_summary": root_dir / "logs" / "session_summary.json",
            "raw_scan": root_dir / "logs" / "raw_scan.jsonl",
        }
        
        # Keep track of file read positions
        self.file_positions = {key: 0 for key in self.log_paths}
        
        # Track initial read so we can pre-populate instead of only showing new updates
        self.is_initial = True
        
        # Device registry for discovered BLE devices
        self._discovered_devices = {}  # {address: {name, rssi, last_seen}}
        self._device_emit_interval = 2.0  # seconds
        self._last_device_emit = 0.0
        self._device_stale_timeout = 60.0  # remove devices not seen for 60s

    def run(self):
        while self.running:
            try:
                self.process_logs()
            except Exception as e:
                print(f"[LogReader ERROR] {e}", file=sys.stderr)
            
            self.is_initial = False
            # Sleep 500ms
            time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()

    def process_logs(self):
        # 1. Read Filtered Scan RSSI
        self._tail_log("filtered_scan", self._handle_rssi)
        
        # 2. Read Spatial Events
        self._tail_log("spatial_events", self._handle_spatial)
        
        # 3. Read Gesture Events
        self._tail_log("gesture_events", self._handle_gesture)
        
        # 4. Read Action Log
        self._tail_log("action_log", self._handle_action_log)
        
        # 5. Read Safety Blocks
        self._tail_log("safety_blocks", self._handle_safety_block)
        
        # 6. Read Context Events
        self._tail_log("context_events", self._handle_context)
        
        # 7. Read Session Summary (JSON file, not jsonl - check modification time or read occasionally)
        self._read_session_summary()
        
        # 8. Read Raw Scan for device discovery
        self._tail_log("raw_scan", self._handle_raw_scan)
        self._emit_devices_if_due()

    def _tail_log(self, key, line_handler):
        path = self.log_paths[key]
        if not path.exists():
            return
            
        file_size = path.stat().st_size
        
        # If file was truncated/recreated, reset position
        if file_size < self.file_positions[key]:
            self.file_positions[key] = 0
            
        # If no new data, skip
        if file_size == self.file_positions[key]:
            return
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(self.file_positions[key])
                lines = f.readlines()
                self.file_positions[key] = f.tell()
                
                # If this is the initial scan on startup, only process the last few lines
                # to populate history, avoiding flooding or parsing huge logs.
                if self.is_initial and len(lines) > 100:
                    lines = lines[-100:]
                    
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        line_handler(data)
                    except json.JSONDecodeError:
                        pass  # Handle malformed lines gracefully
        except Exception as e:
            print(f"[LogReader tail error on {key}] {e}", file=sys.stderr)

    def _read_session_summary(self):
        path = self.log_paths["session_summary"]
        if not path.exists():
            return
            
        # Compare mtime to avoid reading on every loop
        mtime = path.stat().st_mtime
        last_mtime = getattr(self, "_session_last_mtime", 0.0)
        if mtime > last_mtime:
            self._session_last_mtime = mtime
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.session_updated.emit(data)
            except Exception as e:
                pass

    @staticmethod
    def _safe_float(val, default=0.0):
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_timestamp(val, default=None):
        """Parse a timestamp that may be a float epoch or an ISO string."""
        if default is None:
            default = time.time()
        if val is None:
            return default
        # If it's already a number, return as float
        if isinstance(val, (int, float)):
            return float(val)
        # Try ISO string
        if isinstance(val, str):
            try:
                from datetime import datetime
                return datetime.fromisoformat(val).timestamp()
            except (ValueError, TypeError):
                pass
        return default

    # --- Handlers ---
    def _handle_rssi(self, data):
        # Format: {"timestamp": float_or_iso, "raw_rssi": -50, "filtered_rssi": -52.4}
        ts = self._parse_timestamp(data.get("timestamp"))
        raw = self._safe_float(data.get("raw_rssi"), -127.0)
        filt = self._safe_float(data.get("filtered_rssi"), -127.0)
        self.rssi_updated.emit(raw, filt, ts)

    def _handle_spatial(self, data):
        # Format: {"timestamp": ..., "state": "APPROACHING", "confidence": ...} or {"new_state": "APPROACHING"}
        ts = self._parse_timestamp(data.get("timestamp"))
        state = data.get("state") or data.get("new_state", "ABSENT")
        conf = self._safe_float(data.get("confidence"), 1.0)
        self.spatial_state_changed.emit(state, conf, ts)

    def _handle_gesture(self, data):
        # Format: {"timestamp": float_or_iso, "gesture": "ROTATION", "confidence": 0.94}
        ts = self._parse_timestamp(data.get("timestamp"))
        gest = data.get("gesture", "None")
        conf = self._safe_float(data.get("confidence"), 1.0)
        self.gesture_detected.emit(gest, conf, ts)

    def _handle_action_log(self, data):
        # Format: {"timestamp": float_or_iso, "action": "VOLUME_ADJUST", "result": "SUCCESS", "details": "Volume: 68% -> 78%"}
        ts = self._parse_timestamp(data.get("timestamp"))
        action = data.get("action", "None")
        result = data.get("result", "SUCCESS")
        details = data.get("details", "")
        # Normalize result display
        res_str = "✓" if result.upper() == "SUCCESS" else "✗"
        self.action_executed.emit(action, res_str, details, ts)

    def _handle_safety_block(self, data):
        # Format: {"timestamp": float_or_iso, "action": "LOCK_SCREEN", "reason": "Confidence 45% below 70% threshold"}
        ts = self._parse_timestamp(data.get("timestamp"))
        action = data.get("action", "None")
        reason = data.get("reason", "")
        self.action_executed.emit(action, "✗", f"BLOCKED: {reason}", ts)

    def _handle_context(self, data):
        # Live format: {"from": ..., "to": "WORK_MODE", "reason": "...", "timestamp": "2026-..."}
        # Demo format: {"previous_context": ..., "new_context": "WORK_MODE", "reason": "...", "timestamp": float}
        ts_raw = data.get("timestamp", time.time())
        # Handle ISO string timestamps from context_detector
        if isinstance(ts_raw, str):
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts_raw).timestamp()
            except (ValueError, TypeError):
                ts = time.time()
        else:
            ts = self._safe_float(ts_raw, time.time())
        # Support both key naming conventions
        ctx = data.get("new_context") or data.get("to", "WORK_MODE")
        reason = data.get("reason", "")
        self.context_changed.emit(ctx, reason, ts)

    def _handle_raw_scan(self, data):
        """Process raw scan entries to build the discovered devices registry."""
        name = data.get("name", "unnamed")
        address = data.get("address", "")
        rssi = self._safe_float(data.get("rssi"), -127.0)
        
        if not address:
            return
        
        self._discovered_devices[address] = {
            "name": name,
            "address": address,
            "rssi": rssi,
            "last_seen": time.time(),
        }

    def _emit_devices_if_due(self):
        """Emit the discovered devices list periodically."""
        now = time.time()
        if now - self._last_device_emit < self._device_emit_interval:
            return
        self._last_device_emit = now
        
        # Prune stale devices
        stale = [addr for addr, info in self._discovered_devices.items()
                 if now - info["last_seen"] > self._device_stale_timeout]
        for addr in stale:
            del self._discovered_devices[addr]
        
        # Build sorted list: named devices first (by RSSI), then unnamed
        devices = list(self._discovered_devices.values())
        named = sorted([d for d in devices if d["name"] != "unnamed"],
                       key=lambda d: d["rssi"], reverse=True)
        unnamed_count = sum(1 for d in devices if d["name"] == "unnamed")
        
        # Emit named devices + summary count of unnamed
        result = []
        for d in named:
            result.append({
                "name": d["name"],
                "address": d["address"],
                "rssi": d["rssi"],
            })
        
        # Add metadata about unnamed count
        if result or unnamed_count > 0:
            # We'll embed the unnamed count as metadata in the list
            self.devices_updated.emit(result)
