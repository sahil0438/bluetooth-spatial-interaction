import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

class DeviceFilter:
    """
    Tails logs/raw_scan.jsonl in real-time, filtering for target device
    and managing connection status events (device_lost, device_found, tracking).
    Supports matching by device name OR BLE address.
    """
    def __init__(self, raw_log_path: Path, target_name: str = None, target_address: str = None):
        self.raw_log_path = Path(raw_log_path)
        self.target_name = target_name
        self.target_address = target_address.upper() if target_address else None
        self.last_seen_time = None
        self.status = "device_lost"  # Start in lost state until first packet
        self.event_queue = asyncio.Queue()
        self.running = False

    def _is_target_device(self, name: str, address: str) -> bool:
        """Check if a scanned device matches the target by address or name."""
        if self.target_address and address:
            return address.upper() == self.target_address
        if self.target_name and name:
            return name == self.target_name
        return False

    async def run(self):
        """Starts the file tailer and status watchdog concurrently."""
        self.running = True
        await asyncio.gather(
            self._tail_log_file(),
            self._watchdog_loop()
        )

    def stop(self):
        """Stops the filter loops."""
        self.running = False

    async def _tail_log_file(self):
        """Tails the raw scan file and queues matching device packets."""
        # Wait until the log file is created by the scanner
        while self.running and not self.raw_log_path.exists():
            await asyncio.sleep(0.5)

        if not self.running:
            return

        with open(self.raw_log_path, "r", encoding="utf-8") as f:
            # Seek to end to process only new entries
            f.seek(0, 2)
            
            while self.running:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.05)
                    continue

                try:
                    data = json.loads(line.strip())
                    name = data.get("name")
                    address = data.get("address")
                    rssi = data.get("rssi")
                    timestamp = data.get("timestamp")

                    if self._is_target_device(name, address):
                        self.last_seen_time = time.time()
                        
                        if self.status == "device_lost":
                            self.status = "device_found"
                            await self.event_queue.put({
                                "status": "device_found",
                                "name": name,
                                "address": address,
                                "rssi": rssi,
                                "timestamp": timestamp
                            })
                            # Transition to tracking after announcing found
                            self.status = "tracking"
                        else:
                            self.status = "tracking"
                            await self.event_queue.put({
                                "status": "tracking",
                                "name": name,
                                "address": address,
                                "rssi": rssi,
                                "timestamp": timestamp
                            })
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Skip malformed lines
                    continue

    async def _watchdog_loop(self):
        """Periodically checks if the target device is lost (>5 seconds of inactivity)."""
        while self.running:
            await asyncio.sleep(0.5)
            
            # If we are tracking and exceed the timeout, transition to device_lost
            if self.status == "tracking" and self.last_seen_time is not None:
                if time.time() - self.last_seen_time > 5.0:
                    self.status = "device_lost"
                    await self.event_queue.put({
                        "status": "device_lost",
                        "name": self.target_name,
                        "address": None,
                        "rssi": None,
                        "timestamp": datetime.now().isoformat()
                    })

if __name__ == "__main__":
    # Test script to verify it compiles and runs standalone
    print("DeviceFilter loaded successfully. Test running in background.")
    # Setup dummy paths for standalone check
    temp_log = Path("logs/raw_scan_temp_test.jsonl")
    df = DeviceFilter(temp_log)
    print("DeviceFilter instance created.")
