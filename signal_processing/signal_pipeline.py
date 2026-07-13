import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from .moving_average import MovingAverage
from .kalman_filter import KalmanFilter1D
from .device_filter import DeviceFilter

class SignalPipeline:
    """
    Coordinates BLE device filtering, moving average smoothing, and Kalman filtering.
    """
    def __init__(self, raw_log_path: Path, filtered_log_path: Path, target_name: str = None, target_address: str = None):
        self.raw_log_path = Path(raw_log_path)
        self.filtered_log_path = Path(filtered_log_path)
        self.target_name = target_name
        self.target_address = target_address
        
        # Instantiate filters
        self.moving_average = MovingAverage(window_size=5)
        self.kalman_filter = KalmanFilter1D(q=0.008, r=2.0, x0=-62.0, p0=1.0)
        
        # State tracking
        self.last_seen_time = None
        self.status = "device_lost"
        
        self.device_filter = DeviceFilter(self.raw_log_path, self.target_name, self.target_address)
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Ensures the directory for the filtered log exists."""
        self.filtered_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_to_filtered_log(self, payload: dict):
        """Appends a processed reading as a line in the filtered log file."""
        try:
            with open(self.filtered_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            print(f"Error writing to filtered log: {e}")

    def process_new_reading(self, name: str, rssi: float, timestamp: str) -> dict:
        """
        Processes a single raw scan packet.
        Applies filters sequentially (Raw -> Moving Average -> Kalman) for NISHANT.
        """
        if name != self.target_name:
            return None

        self.last_seen_time = time.time()
        
        # Determine status transitions
        if self.status == "device_lost":
            current_status = "device_found"
            self.status = "tracking"
        else:
            current_status = "tracking"
            self.status = "tracking"

        # Apply sequential filtering
        ma_rssi = self.moving_average.update(rssi)
        filtered_rssi = self.kalman_filter.update(ma_rssi)

        payload = {
            "timestamp": timestamp,
            "raw_rssi": rssi,
            "filtered_rssi": round(filtered_rssi, 4),
            "status": current_status
        }

        self._write_to_filtered_log(payload)
        return payload

    async def run(self):
        """Tails the raw scan logs, processes NISHANT data, and logs filtered outputs."""
        print(f"Starting Signal Pipeline. Reading from: {self.raw_log_path}")
        print(f"Writing filtered results to: {self.filtered_log_path}")
        
        # Start device filter monitoring tasks
        filter_task = asyncio.create_task(self.device_filter.run())
        
        try:
            while True:
                # Retrieve filtered events from DeviceFilter queue
                event = await self.device_filter.event_queue.get()
                status = event.get("status")
                timestamp = event.get("timestamp")
                
                if status == "device_lost":
                    # Device disappeared; propagate state
                    self.status = "device_lost"
                    self.moving_average.reset()
                    self.kalman_filter.reset()
                    
                    payload = {
                        "timestamp": timestamp,
                        "raw_rssi": None,
                        "filtered_rssi": None,
                        "status": "device_lost"
                    }
                    self._write_to_filtered_log(payload)
                    
                elif status in ("device_found", "tracking"):
                    rssi = event.get("rssi")
                    
                    # Update filter state
                    self.last_seen_time = time.time()
                    self.status = "tracking"
                    
                    ma_rssi = self.moving_average.update(rssi)
                    filtered_rssi = self.kalman_filter.update(ma_rssi)
                    
                    payload = {
                        "timestamp": timestamp,
                        "raw_rssi": rssi,
                        "filtered_rssi": round(filtered_rssi, 4),
                        "status": status
                    }
                    self._write_to_filtered_log(payload)
                    
                self.device_filter.event_queue.task_done()
                
        except asyncio.CancelledError:
            self.device_filter.stop()
            await filter_task

# Helper factory function to export process_new_reading
_global_pipeline = None

def init_global_pipeline(raw_log: Path, filtered_log: Path, target: str = None, target_address: str = None):
    global _global_pipeline
    _global_pipeline = SignalPipeline(raw_log, filtered_log, target, target_address)

def process_new_reading(name: str, rssi: float, timestamp: str) -> dict:
    global _global_pipeline
    if _global_pipeline is None:
        raise ValueError("Global pipeline is not initialized. Call init_global_pipeline first.")
    return _global_pipeline.process_new_reading(name, rssi, timestamp)
