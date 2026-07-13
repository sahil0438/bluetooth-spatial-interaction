import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner
from bleak.exc import BleakBluetoothNotAvailableError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Configure logging (file-only to keep terminal clean)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# After this many seconds without being seen, a device is removed from the table
DEVICE_TIMEOUT = 30.0
# How often the device table refreshes on screen (seconds)
DISPLAY_REFRESH = 0.3


class BleScanner:
    """
    BLE scanner with a single, unified screen-clearing device table.
    
    Every DISPLAY_REFRESH seconds, the screen clears and redraws the full table.
    Each device appears exactly ONCE showing its latest RSSI. The target device
    is highlighted with >>> and a signal strength bar.
    """
    def __init__(self, output_dir: Path = None, target_name: str = None, target_address: str = None):
        if output_dir is None:
            self.output_dir = Path(__file__).parent.parent / "logs"
        else:
            self.output_dir = Path(output_dir)

        self.output_file = self.output_dir / "raw_scan.jsonl"
        self._ensure_output_dir()
        self.scanning = False

        # Target device info
        self.target_name = target_name
        self.target_address = target_address.upper() if target_address else None

        # Live device tracking: {address: {name, rssi, last_seen, tx_power}}
        self._devices = {}

        # Filtered RSSI data from the visualizer (set externally)
        self.filtered_rssi = None
        self.target_status = "waiting"

        # Spatial state tracking (set externally)
        self.spatial_state = "ABSENT"
        self.spatial_confidence = 100.0
        self.spatial_trend = "STABLE"
        self.spatial_slope = 0.0
        self.spatial_last_change = time.time()

        # Gesture tracking (set externally)
        self.last_gesture_name = None
        self.last_gesture_confidence = 0.0
        self.last_gesture_time = 0.0

        # Context tracking (set externally by Phase 5)
        self.context_name = "WORK_MODE"
        self.context_active_since = 0.0
        self.last_action_name = None
        self.last_action_time = 0.0

    def _ensure_output_dir(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _serialize_manufacturer_data(self, manufacturer_data: dict) -> dict:
        serialized = {}
        for company_id, data in manufacturer_data.items():
            serialized[str(company_id)] = data.hex()
        return serialized

    def _is_target(self, name: str, address: str) -> bool:
        if self.target_address and address:
            if address.upper() == self.target_address:
                return True
        if self.target_name and name:
            if name == self.target_name:
                return True
        return False

    @staticmethod
    def _make_signal_bar(rssi: float, max_len: int = 25) -> str:
        """ASCII signal strength bar for -100 to -30 dBm range."""
        if rssi is None:
            return "░" * max_len
        val = max(-100.0, min(-30.0, float(rssi)))
        pct = (val - (-100.0)) / 70.0
        filled = int(pct * max_len)
        try:
            "█".encode(sys.stdout.encoding or "utf-8")
            return ("█" * filled) + ("░" * (max_len - filled))
        except Exception:
            return ("#" * filled) + ("-" * (max_len - filled))

    def detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Callback for every BLE advertisement — updates device dict and writes log."""
        name = device.name if device.name else "unnamed"
        address = device.address
        rssi = advertisement_data.rssi
        mfg_data = self._serialize_manufacturer_data(advertisement_data.manufacturer_data)

        # Update live device dict
        self._devices[address] = {
            "name": name,
            "rssi": rssi,
            "last_seen": time.time(),
            "tx_power": advertisement_data.tx_power,
        }

        # Write to JSONL log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "address": address,
            "rssi": rssi,
            "manufacturer_data": mfg_data,
            "tx_power": advertisement_data.tx_power
        }
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log entry: {e}")

    def _prune_stale(self):
        """Remove devices not seen within DEVICE_TIMEOUT."""
        now = time.time()
        stale = [a for a, d in self._devices.items() if now - d["last_seen"] > DEVICE_TIMEOUT]
        for a in stale:
            del self._devices[a]

    def _render(self):
        """Clear screen and redraw the full device table."""
        self._prune_stale()
        os.system("cls" if os.name == "nt" else "clear")

        now = time.time()
        named_count = sum(1 for d in self._devices.values() if d["name"] != "unnamed")

        # ── Header ──
        print("=" * 85)
        print("              BLE DEVICE SCANNER — LIVE DEVICE TABLE")
        print("=" * 85)
        print(f"  Refresh: {datetime.now().strftime('%H:%M:%S')}  |  "
              f"Devices: {len(self._devices)} ({named_count} named)  |  "
              f"Stale timeout: {int(DEVICE_TIMEOUT)}s")
        if self.target_name:
            print(f"  Target : {self.target_name}  (highlighted with >>>)")
        elif self.target_address:
            print(f"  Target : {self.target_address}  (highlighted with >>>)")

        # ── Target signal section ──
        target_device = None
        for addr, info in self._devices.items():
            if self._is_target(info["name"], addr):
                target_device = (addr, info)
                break

        print("-" * 85)
        if target_device:
            addr, info = target_device
            raw_rssi = info["rssi"]
            bar = self._make_signal_bar(raw_rssi)
            filt_str = f"{self.filtered_rssi:.1f} dBm" if self.filtered_rssi is not None else "N/A"
            age = int(now - info["last_seen"])
            age_str = "now" if age < 1 else f"{age}s ago"
            print(f"  TARGET SIGNAL:  [{bar}]  Raw: {raw_rssi} dBm  |  Filtered: {filt_str}  |  {age_str}")
        else:
            status_msg = self.target_status.upper()
            if status_msg == "DEVICE_LOST":
                print(f"  TARGET SIGNAL:  ⚠  Target not detected — scanning...")
            else:
                print(f"  TARGET SIGNAL:  Waiting for target device...")

        # ── Spatial State Box ──
        elapsed_change = int(now - self.spatial_last_change)
        elapsed_change_str = f"{elapsed_change}s ago"
        
        state_line = f"SPATIAL STATE: {self.spatial_state}"
        conf_line = f"Confidence:    {self.spatial_confidence:.1f}%"
        slope_str = f"{self.spatial_slope:+.1f}" if self.spatial_slope != 0 else "0.0"
        trend_line = f"Trend:         {self.spatial_trend} (slope: {slope_str})"
        change_line = f"Last change:   {elapsed_change_str}"
        
        print("  ┌─────────────────────────────────────┐")
        print(f"  │ {state_line:35s} │")
        print(f"  │ {conf_line:35s} │")
        print(f"  │ {trend_line:35s} │")
        print(f"  │ {change_line:35s} │")
        print("  └─────────────────────────────────────┘")

        # ── Context Info Box (Phase 5) ──
        # Build gesture + action summary line
        gesture_action_str = "---"
        if self.last_gesture_name is not None:
            gesture_age = int(now - self.last_gesture_time)
            gesture_age_str = "just now" if gesture_age < 2 else f"{gesture_age}s ago"
            # Build short action label
            action_labels = {
                "VOLUME_ADJUST": "VOL+", "LOCK_SCREEN": "LOCK",
                "WAKE_SCREEN": "WAKE", "NEXT_SLIDE": "NEXT",
                "PREV_SLIDE": "PREV", "EXIT_PRESENTATION": "EXIT-PRES",
                "TOGGLE_DND": "DND", "EXIT_FOCUS": "EXIT-FOCUS",
                "NO_ACTION": "---",
            }
            action_short = action_labels.get(self.last_action_name or "", "")
            if action_short:
                gesture_action_str = f"{self.last_gesture_name} ({self.last_gesture_confidence:.1f}%) -> {action_short}"
            else:
                gesture_action_str = f"{self.last_gesture_name} ({self.last_gesture_confidence:.1f}%)"

        # Format context duration
        ctx_dur = int(self.context_active_since)
        ctx_min = ctx_dur // 60
        ctx_sec = ctx_dur % 60
        ctx_dur_str = f"{ctx_min}m {ctx_sec:02d}s" if ctx_min > 0 else f"{ctx_sec}s"

        # Last action age
        last_action_str = "---"
        if self.last_action_name is not None and self.last_action_time > 0:
            action_age = int(now - self.last_action_time)
            action_age_str = "just now" if action_age < 2 else f"{action_age}s ago"
            last_action_str = f"{self.last_action_name} {action_age_str}"

        ctx_line1 = f"CONTEXT:      {self.context_name}"
        ctx_line2 = f"Active for:   {ctx_dur_str}"
        ctx_line3 = f"Last gesture: {gesture_action_str}"
        ctx_line4 = f"Last action:  {last_action_str}"

        # Truncate long lines to fit box width
        box_w = 41
        inner_w = box_w - 4  # "  | " prefix + " |" suffix
        print("  +" + "-" * (box_w - 2) + "+")
        print(f"  | {ctx_line1[:inner_w]:{inner_w}s} |")
        print(f"  | {ctx_line2[:inner_w]:{inner_w}s} |")
        print(f"  | {ctx_line3[:inner_w]:{inner_w}s} |")
        print(f"  | {ctx_line4[:inner_w]:{inner_w}s} |")
        print("  +" + "-" * (box_w - 2) + "+")

        # ── Device table ──
        print("-" * 85)
        print(f"  {'':3s}  {'Name':30s}  {'Address':20s}  {'RSSI':>8s}  {'Seen':>6s}")
        print(f"  {'':3s}  {'─' * 30}  {'─' * 20}  {'─' * 8}  {'─' * 6}")

        if not self._devices:
            print("\n     No devices found yet. Scanning...\n")
        else:
            # Sort: target first, then by RSSI (strongest first)
            sorted_devs = sorted(
                self._devices.items(),
                key=lambda x: (0 if self._is_target(x[1]["name"], x[0]) else 1, -x[1]["rssi"])
            )
            for address, info in sorted_devs:
                name = info["name"]
                rssi = info["rssi"]
                seconds_ago = int(now - info["last_seen"])
                is_tgt = self._is_target(name, address)
                marker = ">>>" if is_tgt else "   "
                display_name = (name[:28] + "..") if len(name) > 30 else name
                age_str = "now" if seconds_ago < 1 else f"{seconds_ago}s"
                print(f"  {marker}  {display_name:30s}  {address:20s}  {rssi:>5d} dB  {age_str:>5s}")

        # ── Footer ──
        print("-" * 85)
        print("  Press Ctrl+C to stop.  |  Table refreshes every "
              f"{DISPLAY_REFRESH:.0f}s  |  Devices disappear after {int(DEVICE_TIMEOUT)}s")
        print("=" * 85)

    async def _display_loop(self):
        """Clears and redraws the device table periodically."""
        while self.scanning:
            if getattr(self, "render_enabled", True):
                self._render()
            await asyncio.sleep(DISPLAY_REFRESH)

    async def run(self):
        """Main scanning loop."""
        logger.info(f"Starting BLE Scanner. Logs: {self.output_file}")
        self.scanning = True

        scanner = BleakScanner(detection_callback=self.detection_callback)
        try:
            async with scanner:
                await self._display_loop()
        except BleakBluetoothNotAvailableError as e:
            logger.error("Bluetooth not available. Turn on Bluetooth.")
            self.scanning = False
            raise e

    def stop(self):
        self.scanning = False
        logger.info("BLE Scanner stopped.")


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    scanner_inst = BleScanner()
    try:
        asyncio.run(scanner_inst.run())
    except KeyboardInterrupt:
        scanner_inst.stop()
        print("\nScanner stopped by user.")
