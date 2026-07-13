"""
Gesture Data Collection Script for Phase 4.

Run main.py in a SEPARATE terminal first, then run this script.
This script tails logs/filtered_scan.jsonl to capture live filtered RSSI values.

IMPORTANT — Timestamp-Aware Collection:
  BLE advertisements arrive at IRREGULAR intervals (3-10+ seconds),
  not every 0.5s. This script captures ONLY genuinely new readings
  during the recording window, then interpolates them to 8 evenly-spaced
  values so the feature extractor always gets a clean temporal sequence.

Usage:
    python -m data_collection.collect_gestures
"""
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

# Gesture labels
GESTURES = {
    "1": "ROTATION",
    "2": "SLOW_DEPARTURE",
    "3": "DOUBLE_APPROACH",
    "4": "IDLE"
}

# Recording parameters
RECORDING_DURATION = 4.0   # seconds — physical gesture window
READINGS_PER_SAMPLE = 8    # final output size after interpolation
MIN_SAMPLES_PER_GESTURE = 50

# Polling interval for tailing the log file (fast enough to catch all BLE ads)
TAIL_POLL_INTERVAL = 0.05  # 50ms

# File paths
ROOT_DIR = Path(__file__).parent.parent
FILTERED_LOG = ROOT_DIR / "logs" / "filtered_scan.jsonl"
CSV_OUTPUT = Path(__file__).parent / "gesture_data.csv"


def get_sample_counts() -> dict:
    """Count existing samples per gesture label in the CSV file."""
    counts = {name: 0 for name in GESTURES.values()}
    if not CSV_OUTPUT.exists():
        return counts
    try:
        with open(CSV_OUTPUT, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                if row and row[0] in counts:
                    counts[row[0]] += 1
    except Exception:
        pass
    return counts


def print_sample_counts(counts: dict):
    """Display current sample counts with warnings."""
    print("\n  Current sample counts:")
    all_sufficient = True
    for gesture, count in counts.items():
        status = "OK" if count >= MIN_SAMPLES_PER_GESTURE else "NEED MORE"
        if count < MIN_SAMPLES_PER_GESTURE:
            all_sufficient = False
        print(f"    {gesture:20s}: {count:4d} samples  [{status}]")
    if all_sufficient:
        print("  All gestures have sufficient samples for training.")
    else:
        needed = {g: max(0, MIN_SAMPLES_PER_GESTURE - c) for g, c in counts.items()}
        total_needed = sum(needed.values())
        print(f"  WARNING: {total_needed} more samples needed before training.")
    print()


def ensure_csv_header():
    """Create CSV file with header if it doesn't exist."""
    if not CSV_OUTPUT.exists():
        CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["label", "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"])


def interpolate_to_fixed_size(timestamps: list, values: list, num_points: int = 8) -> list:
    """
    Interpolate irregularly-spaced (timestamp, rssi) pairs into
    `num_points` evenly-spaced values across the full time span.

    If only 1 reading was captured, returns that value repeated.
    If 0 readings, returns None (recording failed).
    """
    if len(values) == 0:
        return None

    if len(values) == 1:
        # Only one reading — replicate it (essentially flat/no-data)
        return [round(values[0], 2)] * num_points

    ts = np.array(timestamps)
    vs = np.array(values)

    # Create evenly-spaced target timestamps across the full window
    t_start = ts[0]
    t_end = ts[-1]

    # If all readings arrived at nearly the same instant, spread them out
    if t_end - t_start < 0.1:
        return [round(float(v), 2) for v in np.linspace(vs[0], vs[-1], num_points)]

    t_uniform = np.linspace(t_start, t_end, num_points)

    # Linear interpolation
    interpolated = np.interp(t_uniform, ts, vs)

    return [round(float(v), 2) for v in interpolated]


def record_gesture(label: str) -> tuple:
    """
    Countdown 3 seconds, then record for RECORDING_DURATION seconds.

    Instead of polling the last value every 0.5s, this tails the filtered log
    and captures ONLY genuinely new entries with their real arrival timestamps.

    Returns:
        (interpolated_readings, raw_count) — list of 8 floats + count of real BLE readings,
        or (None, 0) if recording failed.
    """
    if not FILTERED_LOG.exists():
        print("  [ERROR] Filtered log not found. Is main.py running?")
        return None, 0

    # Countdown
    print(f"\n  Recording: {label}")
    for i in range(3, 0, -1):
        print(f"    Starting in {i}...", flush=True)
        time.sleep(1.0)

    print("    >>> RECORDING NOW <<<", flush=True)

    # Seek to end of the filtered log BEFORE recording starts
    # so we only capture entries that arrive DURING the window
    with open(FILTERED_LOG, "r", encoding="utf-8") as f:
        f.seek(0, 2)  # seek to end

        raw_timestamps = []   # time offset from recording start
        raw_values = []       # actual filtered RSSI values
        start_time = time.time()
        last_value = None     # to detect genuinely new readings

        while True:
            elapsed = time.time() - start_time
            if elapsed >= RECORDING_DURATION:
                break

            line = f.readline()
            if line:
                try:
                    data = json.loads(line.strip())
                    filtered = data.get("filtered_rssi")
                    if filtered is not None and filtered != -127.0:
                        # Only record if this is a genuinely different value
                        # (small tolerance to catch real new readings vs float noise)
                        if last_value is None or abs(filtered - last_value) > 0.001:
                            raw_timestamps.append(elapsed)
                            raw_values.append(filtered)
                            last_value = filtered

                            # Show live progress
                            bar_filled = int((elapsed / RECORDING_DURATION) * 20)
                            bar = "=" * bar_filled + ">" + " " * (20 - bar_filled)
                            print(f"    [{bar}] {elapsed:.1f}s  NEW RSSI: {filtered:.1f} dBm  "
                                  f"(readings: {len(raw_values)})", flush=True)
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
            else:
                time.sleep(TAIL_POLL_INTERVAL)

    raw_count = len(raw_values)
    print(f"    >>> RECORDING COMPLETE <<<")
    print(f"    Captured {raw_count} unique BLE readings in {RECORDING_DURATION:.0f}s")

    if raw_count == 0:
        print("    [WARNING] No new RSSI readings received! Is the target device nearby?")
        return None, 0

    if raw_count == 1:
        print("    [WARNING] Only 1 reading captured — very low BLE update rate.")
        print("    The sample will be flat (all 8 values identical).")

    # Interpolate to 8 evenly-spaced values
    interpolated = interpolate_to_fixed_size(raw_timestamps, raw_values, READINGS_PER_SAMPLE)

    if interpolated is None:
        return None, 0

    return interpolated, raw_count


def save_sample(label: str, readings: list):
    """Append a single sample (label + 8 readings) to the CSV file."""
    ensure_csv_header()
    with open(CSV_OUTPUT, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([label] + readings)


def print_menu():
    """Show the main menu."""
    print("=" * 60)
    print("       GESTURE DATA COLLECTION — Phase 4 (v2)")
    print("       Timestamp-Aware + Interpolation")
    print("=" * 60)
    print()
    print("  Select gesture to record:")
    print("  [1] ROTATION         — dip-recover wave x2")
    print("  [2] SLOW_DEPARTURE   — gradual walk away")
    print("  [3] DOUBLE_APPROACH  — approach, pause, approach again")
    print("  [4] IDLE             — sit still, no motion")
    print("  [Q] Quit")
    print()


def print_quality_assessment(raw_count: int, readings: list):
    """Show data quality info based on how many real readings were captured."""
    print(f"\n  Data quality assessment:")
    if raw_count >= 6:
        quality = "EXCELLENT"
        msg = "Plenty of real data points — interpolation is very accurate."
    elif raw_count >= 4:
        quality = "GOOD"
        msg = "Enough data points for reliable interpolation."
    elif raw_count >= 2:
        quality = "FAIR"
        msg = "Limited readings — interpolation fills the gaps but may miss details."
    else:
        quality = "POOR"
        msg = "Only 1 reading — sample is flat. Consider discarding."

    print(f"    Real BLE readings: {raw_count}  →  Quality: {quality}")
    print(f"    {msg}")

    rssi_min = min(readings)
    rssi_max = max(readings)
    rssi_range = rssi_max - rssi_min
    print(f"    Interpolated range: {rssi_min:.1f} to {rssi_max:.1f} dBm (variation: {rssi_range:.1f} dBm)")


def main():
    """Main collection loop."""
    # Check if filtered log exists
    if not FILTERED_LOG.exists():
        print("[ERROR] logs/filtered_scan.jsonl not found.")
        print("Start main.py in a SEPARATE terminal first, then run this script.")
        sys.exit(1)

    # Check if we can read a value
    print("[INFO] Timestamp-aware collection mode enabled.")
    print("[INFO] This version captures only REAL new BLE readings and interpolates.")
    print("[INFO] You will see how many actual readings were captured per sample.\n")

    ensure_csv_header()

    while True:
        counts = get_sample_counts()
        print_menu()
        print_sample_counts(counts)

        choice = input("  Enter choice: ").strip().upper()

        if choice == "Q":
            print("\n  Exiting data collection.")
            # Final warning check
            counts = get_sample_counts()
            insufficient = [g for g, c in counts.items() if c < MIN_SAMPLES_PER_GESTURE]
            if insufficient:
                print(f"  WARNING: These gestures still need more samples: {', '.join(insufficient)}")
                print(f"  Minimum required: {MIN_SAMPLES_PER_GESTURE} per gesture.")
            else:
                total = sum(counts.values())
                print(f"  All gestures have sufficient samples ({total} total). Ready to train!")
                print(f"  Run: python -m gesture_engine.train_model")
            break

        if choice not in GESTURES:
            print("  Invalid choice. Try again.\n")
            continue

        label = GESTURES[choice]

        # Record the gesture
        readings, raw_count = record_gesture(label)

        if readings is None:
            print("  Recording failed. Try again.\n")
            continue

        # Show captured data
        print(f"\n  Captured sequence for {label}:")
        print(f"    Raw BLE readings: {raw_count}")
        print(f"    Interpolated (8 values): {readings}")

        # Quality assessment
        print_quality_assessment(raw_count, readings)

        # Ask to save
        save_choice = input("\n  Save this sample? (y/n): ").strip().lower()
        if save_choice == "y":
            save_sample(label, readings)
            counts = get_sample_counts()
            print(f"  Saved! {label} now has {counts[label]} samples.")
        else:
            print("  Discarded.")

        print()


if __name__ == "__main__":
    main()
