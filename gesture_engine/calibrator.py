import json
import time
import sys
import asyncio
from datetime import datetime
from pathlib import Path
import numpy as np

class Calibrator:
    """
    Handles baseline RSSI calibration for the tracking target.
    Can load existing calibration or run a 10-second calibration phase.
    """
    def __init__(self, filtered_log_path: Path, calibration_path: Path):
        self.filtered_log_path = Path(filtered_log_path)
        self.calibration_path = Path(calibration_path)

    def is_calibrated(self) -> bool:
        """Checks if a valid calibration file exists."""
        return self.calibration_path.exists()

    def load_calibration(self) -> dict:
        """Loads and returns the existing calibration from disk."""
        if self.is_calibrated():
            try:
                with open(self.calibration_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"Loaded existing calibration. Baseline: {data.get('baseline_rssi')} dBm | Noise floor: ±{data.get('rssi_noise_floor')} dBm | Ready.")
                    return data
            except Exception as e:
                print(f"[WARNING] Failed to load calibration.json: {e}. Re-calibrating.")
        return None

    async def run_calibration(self, duration: float = 10.0) -> dict:
        """
        Runs the 10-second calibration by tailing the filtered scan log.
        Calculates baseline_rssi (mean), rssi_noise_floor (std dev), and absent_threshold.
        """
        print("=" * 60)
        print(f"STARTING CALIBRATION: Collecting readings for {duration} seconds...")
        print("Please stay still at your desk (working distance).")
        print("=" * 60)
        
        # Ensure log directory and file exist
        self.filtered_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.filtered_log_path.exists():
            self.filtered_log_path.touch()

        start_time = time.time()
        readings = []

        with open(self.filtered_log_path, "r", encoding="utf-8") as f:
            # Go to current end of file to ignore past runs
            f.seek(0, 2)
            
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time
                remaining = max(0.0, duration - elapsed)
                sys.stdout.write(f"\rCalibrating... {remaining:.1f}s remaining. Collected {len(readings)} readings.")
                sys.stdout.flush()
                
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    data = json.loads(line.strip())
                    if data.get("status") in ("tracking", "device_found"):
                        val = data.get("filtered_rssi")
                        if val is not None and val != -127:
                            readings.append(val)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            # Final check to read any remaining lines that came in at the very end
            time.sleep(0.1)
            while True:
                line = f.readline()
                if not line:
                    break
                try:
                    data = json.loads(line.strip())
                    if data.get("status") in ("tracking", "device_found"):
                        val = data.get("filtered_rssi")
                        if val is not None and val != -127:
                            readings.append(val)
                except (json.JSONDecodeError, KeyError):
                    continue

            sys.stdout.write("\n")
            sys.stdout.flush()

        # Calculate metrics
        if len(readings) < 3:
            print("\n[WARNING] Too few RSSI readings collected during calibration.")
            print("Ensure Nothing Phone (2a) is advertising and in range.")
            baseline_rssi = -60.0
            rssi_noise_floor = 2.0
            print(f"Using default fallback values. Baseline: {baseline_rssi} dBm | Noise floor: ±{rssi_noise_floor} dBm")
        else:
            baseline_rssi = float(np.mean(readings))
            rssi_noise_floor = float(np.std(readings))
            # Ensure noise floor has a reasonable minimum to prevent division by zero or overly sensitive triggers
            if rssi_noise_floor < 0.5:
                rssi_noise_floor = 0.5

        calibration_data = {
            "baseline_rssi": round(baseline_rssi, 2),
            "rssi_noise_floor": round(rssi_noise_floor, 2),
            "absent_threshold": -100.0,
            "timestamp": datetime.now().isoformat()
        }

        # Save to file
        try:
            self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.calibration_path, "w", encoding="utf-8") as f:
                json.dump(calibration_data, f, indent=4)
            print(f"Calibration complete: Baseline: {calibration_data['baseline_rssi']} dBm | Noise floor: ±{calibration_data['rssi_noise_floor']} dBm | Ready.")
        except Exception as e:
            print(f"[ERROR] Failed to save calibration file: {e}")

        return calibration_data

if __name__ == "__main__":
    # Small test
    root = Path(__file__).parent.parent
    cal = Calibrator(root / "logs" / "filtered_scan.jsonl", root / "logs" / "calibration.json")
    print("Calibrator module test loaded.")
