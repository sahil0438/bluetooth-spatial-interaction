"""
Synthetic Gesture Data Generator for Phase 4.

Generates realistic BLE RSSI sequences for gesture training
WITHOUT requiring a live Bluetooth connection.

Physics-based signal modeling:
  - Log-distance path loss model for approach/departure
  - Body shadowing effects (10-20 dBm attenuation) for rotation
  - Multipath fading (Rician/Rayleigh) small-scale variations
  - BLE advertisement jitter and measurement noise

Usage:
    python -m data_collection.generate_synthetic_data
"""
import csv
import sys
import numpy as np
from pathlib import Path

# ============================================================
#  Configuration
# ============================================================

GESTURES = {
    "ROTATION": 150,
    "SLOW_DEPARTURE": 150,
    "DOUBLE_APPROACH": 150,
    "IDLE": 150,
}

READINGS_PER_SAMPLE = 8          # matches collect_gestures.py
TOTAL_WINDOW_SEC = 4.0           # 4-second gesture window
DT = TOTAL_WINDOW_SEC / (READINGS_PER_SAMPLE - 1)  # ~0.571s per step

# Typical BLE RSSI operating range (dBm)
RSSI_NEAR = -42      # very close, ~0.3m
RSSI_DESK = -58      # typical working distance ~1m
RSSI_MID = -70       # a few metres away
RSSI_FAR = -90       # far / edge of range
RSSI_VERY_FAR = -100 # near absent threshold

# BLE measurement noise (std dev in dBm) — real BLE chips show 2-4 dBm jitter
BLE_NOISE_STD = 2.5

# File paths
CSV_OUTPUT = Path(__file__).parent / "gesture_data.csv"

np.random.seed(None)  # truly random each run


# ============================================================
#  Noise & Realism Helpers
# ============================================================

def add_ble_noise(sequence: np.ndarray, noise_std: float = BLE_NOISE_STD) -> np.ndarray:
    """Add realistic BLE measurement noise."""
    noise = np.random.normal(0, noise_std, len(sequence))
    return sequence + noise


def add_multipath_fading(sequence: np.ndarray, amplitude: float = 3.0) -> np.ndarray:
    """Simulate small-scale multipath fading with random frequency."""
    freq = np.random.uniform(0.5, 2.5)
    phase = np.random.uniform(0, 2 * np.pi)
    t = np.linspace(0, TOTAL_WINDOW_SEC, len(sequence))
    fading = amplitude * np.sin(2 * np.pi * freq * t + phase)
    return sequence + fading


def clamp_rssi(sequence: np.ndarray) -> list:
    """Clamp RSSI to realistic BLE range and round."""
    clamped = np.clip(sequence, -100, -30)
    return [round(float(v), 2) for v in clamped]


# ============================================================
#  Gesture Generators
# ============================================================

def generate_rotation() -> list:
    """
    ROTATION: Dip-recover wave pattern x2 in 4 seconds.

    Physical model: User rotates their body near the laptop.
    Body shadowing causes 10-25 dBm attenuation when body blocks
    the line-of-sight. Two rotation cycles produce two dips.

    Feature signature:
      - dip_count: 1-2 (significant dips >= 8 dBm)
      - dip_depth: 10-25 dBm
      - recovery_strength: high (signal bounces back)
      - slope: ~0 (net position unchanged)
      - momentum: ~0 (starts and ends similar)
    """
    # Baseline RSSI at working distance
    baseline = np.random.uniform(-55, -65)

    # Time array for 8 readings
    t = np.linspace(0, TOTAL_WINDOW_SEC, READINGS_PER_SAMPLE)

    # --- Strategy selection for variety ---
    strategy = np.random.choice(["double_dip", "single_deep_dip", "asymmetric_dip"])

    if strategy == "double_dip":
        # Two clear dip-recover cycles
        dip_depth_1 = np.random.uniform(12, 25)
        dip_depth_2 = np.random.uniform(10, 22)
        # Dips happen at ~1.0s and ~3.0s
        dip_center_1 = np.random.uniform(0.8, 1.3)
        dip_center_2 = np.random.uniform(2.7, 3.3)
        dip_width = np.random.uniform(0.3, 0.6)

        signal = np.full(READINGS_PER_SAMPLE, baseline)
        for i, ti in enumerate(t):
            # Gaussian dip profile
            dip1 = dip_depth_1 * np.exp(-0.5 * ((ti - dip_center_1) / dip_width) ** 2)
            dip2 = dip_depth_2 * np.exp(-0.5 * ((ti - dip_center_2) / dip_width) ** 2)
            signal[i] -= (dip1 + dip2)

    elif strategy == "single_deep_dip":
        # One very pronounced dip with strong recovery
        dip_depth = np.random.uniform(18, 30)
        dip_center = np.random.uniform(1.5, 2.5)
        dip_width = np.random.uniform(0.4, 0.8)

        signal = np.full(READINGS_PER_SAMPLE, baseline)
        for i, ti in enumerate(t):
            dip = dip_depth * np.exp(-0.5 * ((ti - dip_center) / dip_width) ** 2)
            signal[i] -= dip

    else:  # asymmetric_dip
        # Two dips of different depths — one deep, one shallow
        dip_depth_1 = np.random.uniform(15, 28)
        dip_depth_2 = np.random.uniform(8, 14)
        dip_center_1 = np.random.uniform(0.7, 1.5)
        dip_center_2 = np.random.uniform(2.5, 3.5)
        dip_width_1 = np.random.uniform(0.3, 0.5)
        dip_width_2 = np.random.uniform(0.4, 0.7)

        signal = np.full(READINGS_PER_SAMPLE, baseline)
        for i, ti in enumerate(t):
            dip1 = dip_depth_1 * np.exp(-0.5 * ((ti - dip_center_1) / dip_width_1) ** 2)
            dip2 = dip_depth_2 * np.exp(-0.5 * ((ti - dip_center_2) / dip_width_2) ** 2)
            signal[i] -= (dip1 + dip2)

    # Add fading + noise
    signal = add_multipath_fading(signal, amplitude=2.0)
    signal = add_ble_noise(signal, noise_std=2.0)

    return clamp_rssi(signal)


def generate_slow_departure() -> list:
    """
    SLOW_DEPARTURE: Gradual RSSI decline over 4-5 seconds.

    Physical model: User walks away from the laptop at normal pace.
    Log-distance path loss: RSSI decreases ~20*n*log10(d), where n≈2-3.
    Walking speed ~1-1.5 m/s → covers 4-6m in 4s window.

    Feature signature:
      - slope: strongly negative (< -3 dBm/s)
      - momentum: strongly negative (second half much lower)
      - std_rssi: moderate-high
      - dip_count: 0 (monotonic decline)
      - rssi_range: large (20-40 dBm)
    """
    # Starting RSSI (near desk)
    start_rssi = np.random.uniform(-45, -62)

    # Ending RSSI (walked away)
    total_drop = np.random.uniform(20, 42)
    end_rssi = start_rssi - total_drop

    # Clamp ending
    end_rssi = max(end_rssi, -100)

    t = np.linspace(0, 1, READINGS_PER_SAMPLE)

    # --- Strategy selection ---
    strategy = np.random.choice(["linear", "logarithmic", "accelerating"])

    if strategy == "linear":
        # Straight-line decline
        signal = np.linspace(start_rssi, end_rssi, READINGS_PER_SAMPLE)

    elif strategy == "logarithmic":
        # Log-distance path loss model: signal drops faster initially, slows at range
        # RSSI ∝ -10*n*log10(d), so going from 1m to 5m:
        distances = np.linspace(1.0, np.random.uniform(3.5, 7.0), READINGS_PER_SAMPLE)
        path_loss_n = np.random.uniform(2.0, 3.0)
        signal = start_rssi - 10 * path_loss_n * np.log10(distances)

    else:  # accelerating
        # Starts slow, drops faster (user picks up walking speed)
        curve = t ** np.random.uniform(1.3, 2.0)
        signal = start_rssi + curve * (end_rssi - start_rssi)

    # Small occasional uptick from multipath reflection (but overall still declining)
    signal = add_multipath_fading(signal, amplitude=1.5)
    signal = add_ble_noise(signal, noise_std=2.5)

    # Ensure overall decline is preserved (sort check)
    # We don't force monotonic — real departures have minor fluctuations
    return clamp_rssi(signal)


def generate_double_approach() -> list:
    """
    DOUBLE_APPROACH: Approach → pause → approach again.

    Physical model: User walks toward laptop, pauses briefly,
    then continues approaching. Two distinct rising segments with
    a plateau or small dip between them.

    Feature signature:
      - slope: positive (overall approaching)
      - momentum: positive (second half stronger than first)
      - crossing_rate: moderate
      - dip_count: 0-1 (pause can look like a small dip)
      - rssi_range: moderate-large
    """
    # Starting RSSI (far away)
    start_rssi = np.random.uniform(-82, -92)

    # Mid-pause RSSI (after first approach)
    mid_rssi = start_rssi + np.random.uniform(10, 20)

    # Final RSSI (close up)
    end_rssi = mid_rssi + np.random.uniform(10, 22)
    end_rssi = min(end_rssi, -38)

    # Pause timing (which reading is the pause at)
    pause_idx = np.random.choice([3, 4])

    signal = np.zeros(READINGS_PER_SAMPLE)

    # --- Build piecewise ---
    strategy = np.random.choice(["clean_double", "hesitant", "smooth_pause"])

    if strategy == "clean_double":
        # Clear two-phase approach with definite plateau
        phase1 = np.linspace(start_rssi, mid_rssi, pause_idx + 1)
        pause_duration = np.random.choice([1, 2])
        pause_values = np.full(pause_duration, mid_rssi + np.random.uniform(-3, 3))
        remaining = READINGS_PER_SAMPLE - pause_idx - 1 - pause_duration
        if remaining < 1:
            remaining = 1
            pause_duration = READINGS_PER_SAMPLE - pause_idx - 1 - remaining
            pause_values = np.full(max(pause_duration, 0), mid_rssi)
        phase2 = np.linspace(mid_rssi, end_rssi, remaining + 1)[1:]
        combined = np.concatenate([phase1, pause_values, phase2])
        # Trim or pad to exact length
        signal = combined[:READINGS_PER_SAMPLE]
        if len(signal) < READINGS_PER_SAMPLE:
            signal = np.pad(signal, (0, READINGS_PER_SAMPLE - len(signal)),
                          mode='edge')

    elif strategy == "hesitant":
        # First approach, slight retreat, then stronger approach
        phase1 = np.linspace(start_rssi, mid_rssi, pause_idx + 1)
        dip = mid_rssi - np.random.uniform(3, 8)
        phase2_start = np.array([dip])
        remaining = READINGS_PER_SAMPLE - pause_idx - 2
        phase2 = np.linspace(dip, end_rssi, max(remaining, 1) + 1)[1:]
        combined = np.concatenate([phase1, phase2_start, phase2])
        signal = combined[:READINGS_PER_SAMPLE]
        if len(signal) < READINGS_PER_SAMPLE:
            signal = np.pad(signal, (0, READINGS_PER_SAMPLE - len(signal)),
                          mode='edge')

    else:  # smooth_pause
        # Smooth sinusoidal-ish rise with a plateau in the middle
        t_norm = np.linspace(0, 1, READINGS_PER_SAMPLE)
        # S-curve with inflection
        total_range = end_rssi - start_rssi
        # Create a step-like approach
        curve = start_rssi + total_range * (
            0.5 * (np.tanh(6 * (t_norm - 0.25)) + 1) * 0.45 +
            0.5 * (np.tanh(6 * (t_norm - 0.7)) + 1) * 0.55
        )
        signal = curve

    signal = add_multipath_fading(signal, amplitude=2.0)
    signal = add_ble_noise(signal, noise_std=2.0)

    return clamp_rssi(signal)


def generate_idle() -> list:
    """
    IDLE: No significant motion, phone stays at desk distance.

    Physical model: User sitting at desk, phone stationary.
    RSSI fluctuates around baseline due to:
      - Environmental multipath changes (people walking by, doors opening)
      - BLE chip measurement jitter
      - Very slow environmental drift

    Feature signature:
      - std_rssi: LOW (< 4 dBm)
      - slope: ~0 (no trend)
      - momentum: ~0
      - rssi_range: small (< 10 dBm)
      - dip_count: 0
      - crossing_rate: varies (random fluctuations cross mean)
    """
    # Baseline RSSI (stationary at desk)
    baseline = np.random.uniform(-52, -68)

    # --- Strategy selection ---
    strategy = np.random.choice(["flat", "slight_drift", "noisy_flat"])

    if strategy == "flat":
        # Very stable signal
        signal = np.full(READINGS_PER_SAMPLE, baseline)
        signal = add_ble_noise(signal, noise_std=1.8)

    elif strategy == "slight_drift":
        # Tiny linear drift (environment change, but not a gesture)
        drift = np.random.uniform(-3, 3)  # max ±3 dBm over 4s — NOT a departure
        signal = np.linspace(baseline, baseline + drift, READINGS_PER_SAMPLE)
        signal = add_ble_noise(signal, noise_std=2.0)

    else:  # noisy_flat
        # Slightly noisier (environment multipath) but no trend
        signal = np.full(READINGS_PER_SAMPLE, baseline)
        signal = add_multipath_fading(signal, amplitude=1.5)
        signal = add_ble_noise(signal, noise_std=2.5)

    return clamp_rssi(signal)


# ============================================================
#  Generator Dispatch
# ============================================================

GENERATORS = {
    "ROTATION": generate_rotation,
    "SLOW_DEPARTURE": generate_slow_departure,
    "DOUBLE_APPROACH": generate_double_approach,
    "IDLE": generate_idle,
}


# ============================================================
#  Main
# ============================================================

def main():
    """Generate synthetic dataset and save to gesture_data.csv."""
    print("=" * 65)
    print("     SYNTHETIC GESTURE DATA GENERATOR — Phase 4")
    print("     Physics-Based BLE RSSI Simulation")
    print("=" * 65)

    total_samples = sum(GESTURES.values())
    print(f"\n  Target: {total_samples} total samples")
    for gesture, count in GESTURES.items():
        print(f"    {gesture:20s}: {count} samples")

    # Generate all samples
    all_rows = []
    for gesture, count in GESTURES.items():
        print(f"\n  Generating {gesture}...", end="", flush=True)
        for i in range(count):
            readings = GENERATORS[gesture]()
            all_rows.append([gesture] + readings)
        print(f" done ({count} samples)")

    # Shuffle to prevent ordering bias during training
    np.random.shuffle(all_rows)

    # Write CSV
    CSV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"])
        writer.writerows(all_rows)

    print(f"\n  Dataset saved to: {CSV_OUTPUT}")
    print(f"  Total samples: {len(all_rows)}")

    # Quick validation — extract features from a few samples and show stats
    print("\n" + "-" * 65)
    print("  Quick Validation — Sample Feature Check")
    print("-" * 65)

    # Import feature extractor for validation
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from gesture_engine.feature_extractor import extract_features, FEATURE_NAMES

    for gesture in GESTURES:
        gesture_rows = [r for r in all_rows if r[0] == gesture]
        sample = gesture_rows[0]
        features = extract_features(sample[1:])
        print(f"\n  {gesture} (example):")
        print(f"    RSSI sequence: {sample[1:]}")
        for name, val in zip(FEATURE_NAMES, features):
            print(f"      {name:22s}: {val}")

    print("\n" + "=" * 65)
    print("  Dataset generation complete!")
    print(f"  Next step: python -m gesture_engine.train_model")
    print("=" * 65)


if __name__ == "__main__":
    main()
