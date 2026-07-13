"""
Feature Extractor for Gesture Recognition — Phase 4.

Extracts 13 numerical features from a sequence of 8 filtered RSSI readings.
These features are used by the ML model to classify gestures.
"""
import numpy as np

# Feature names in the exact order returned by extract_features()
FEATURE_NAMES = [
    "mean_rssi",
    "std_rssi",
    "slope",
    "min_rssi",
    "max_rssi",
    "rssi_range",
    "dip_count",
    "dip_depth",
    "recovery_strength",
    "crossing_rate",
    "first_half_mean",
    "second_half_mean",
    "momentum"
]


def extract_features(rssi_sequence) -> list:
    """
    Extract 13 features from a sequence of 8 filtered RSSI readings.

    Parameters:
        rssi_sequence: list or array of 8 floats (filtered RSSI values)

    Returns:
        list of 13 floats — one per feature in FEATURE_NAMES order
    """
    seq = np.array(rssi_sequence, dtype=float)
    n = len(seq)

    # 1. mean_rssi — average of all readings
    mean_rssi = float(np.mean(seq))

    # 2. std_rssi — standard deviation
    std_rssi = float(np.std(seq))

    # 3. slope — linear trend via numpy polyfit degree 1
    #    x-axis is time indices (0..n-1), each separated by 0.5s
    x = np.arange(n) * 0.5
    coeffs = np.polyfit(x, seq, 1)
    slope = float(coeffs[0])  # dBm per second

    # 4. min_rssi
    min_rssi = float(np.min(seq))

    # 5. max_rssi
    max_rssi = float(np.max(seq))

    # 6. rssi_range — total variation
    rssi_range = max_rssi - min_rssi

    # 7. dip_count — number of valleys (lower than both neighbours AND
    #    at least 8 dBm below local mean of neighbours)
    dip_count = 0
    dip_depths = []
    dip_recoveries = []
    for i in range(1, n - 1):
        left = seq[i - 1]
        centre = seq[i]
        right = seq[i + 1]
        local_mean = (left + right) / 2.0
        if centre < left and centre < right and (local_mean - centre) >= 8.0:
            dip_count += 1
            depth = local_mean - centre
            dip_depths.append(depth)
            # Recovery strength = how much signal comes back after the dip
            recovery = right - centre
            dip_recoveries.append(recovery)

    # 8. dip_depth — average depth of detected dips
    dip_depth = float(np.mean(dip_depths)) if dip_depths else 0.0

    # 9. recovery_strength — average recovery after each dip
    recovery_strength = float(np.mean(dip_recoveries)) if dip_recoveries else 0.0

    # 10. crossing_rate — how many times RSSI crosses the mean value
    crossing_count = 0
    for i in range(1, n):
        if (seq[i - 1] < mean_rssi and seq[i] >= mean_rssi) or \
           (seq[i - 1] >= mean_rssi and seq[i] < mean_rssi):
            crossing_count += 1
    crossing_rate = float(crossing_count)

    # 11. first_half_mean — mean of readings 0-3
    first_half_mean = float(np.mean(seq[:4]))

    # 12. second_half_mean — mean of readings 4-7
    second_half_mean = float(np.mean(seq[4:8] if n >= 8 else seq[4:]))

    # 13. momentum — second_half_mean - first_half_mean
    #     positive = approaching, negative = departing
    momentum = second_half_mean - first_half_mean

    return [
        round(mean_rssi, 4),
        round(std_rssi, 4),
        round(slope, 4),
        round(min_rssi, 4),
        round(max_rssi, 4),
        round(rssi_range, 4),
        dip_count,
        round(dip_depth, 4),
        round(recovery_strength, 4),
        crossing_rate,
        round(first_half_mean, 4),
        round(second_half_mean, 4),
        round(momentum, 4)
    ]


if __name__ == "__main__":
    print("=" * 60)
    print("Feature Extractor Test — Sample Sequences")
    print("=" * 60)

    # Test 1: Approach sequence (RSSI increasing)
    approach = [-85, -80, -74, -68, -62, -57, -52, -48]
    features = extract_features(approach)
    print(f"\nApproach sequence: {approach}")
    for name, val in zip(FEATURE_NAMES, features):
        print(f"  {name:22s}: {val}")

    # Test 2: Stable/Idle sequence (small variation)
    idle = [-58, -60, -57, -61, -59, -58, -62, -60]
    features = extract_features(idle)
    print(f"\nIdle sequence: {idle}")
    for name, val in zip(FEATURE_NAMES, features):
        print(f"  {name:22s}: {val}")

    # Test 3: Rotation (dip-recover pattern)
    rotation = [-55, -70, -54, -56, -72, -53, -55, -57]
    features = extract_features(rotation)
    print(f"\nRotation sequence: {rotation}")
    for name, val in zip(FEATURE_NAMES, features):
        print(f"  {name:22s}: {val}")

    # Test 4: Departure sequence (RSSI decreasing)
    departure = [-48, -54, -60, -67, -73, -80, -87, -95]
    features = extract_features(departure)
    print(f"\nDeparture sequence: {departure}")
    for name, val in zip(FEATURE_NAMES, features):
        print(f"  {name:22s}: {val}")

    print(f"\nTotal features per sample: {len(FEATURE_NAMES)}")
    print("Feature extraction module is ready.")
