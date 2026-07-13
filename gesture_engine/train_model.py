"""
Model Trainer for Gesture Recognition — Phase 4.

Loads gesture_data.csv, extracts features, trains Random Forest + SVM,
saves the better model.

Usage:
    python -m gesture_engine.train_model
"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

from .feature_extractor import extract_features, FEATURE_NAMES

# Paths
ROOT_DIR = Path(__file__).parent.parent
CSV_PATH = ROOT_DIR / "data_collection" / "gesture_data.csv"
MODEL_DIR = ROOT_DIR / "models"
MODEL_PATH = MODEL_DIR / "gesture_model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
INFO_PATH = MODEL_DIR / "model_info.json"

MIN_SAMPLES_PER_GESTURE = 50


def load_data():
    """Load gesture_data.csv and return labels and raw RSSI sequences."""
    if not CSV_PATH.exists():
        print(f"[ERROR] Data file not found: {CSV_PATH}")
        print("Run data collection first: python -m data_collection.collect_gestures")
        sys.exit(1)

    labels = []
    sequences = []

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header
        for row in reader:
            if len(row) < 9:
                continue
            label = row[0]
            try:
                rssi_seq = [float(x) for x in row[1:9]]
            except ValueError:
                continue
            labels.append(label)
            sequences.append(rssi_seq)

    return labels, sequences


def check_sample_counts(labels):
    """Verify minimum sample counts and print summary."""
    from collections import Counter
    counts = Counter(labels)
    print("\n  Sample counts:")
    all_ok = True
    for gesture in sorted(counts.keys()):
        count = counts[gesture]
        status = "OK" if count >= MIN_SAMPLES_PER_GESTURE else "INSUFFICIENT"
        if count < MIN_SAMPLES_PER_GESTURE:
            all_ok = False
        print(f"    {gesture:20s}: {count:4d}  [{status}]")

    if not all_ok:
        print(f"\n  [ERROR] Each gesture needs at least {MIN_SAMPLES_PER_GESTURE} samples.")
        print("  Collect more data before training.")
        sys.exit(1)

    return dict(counts)


def build_feature_matrix(sequences):
    """Extract features from all sequences."""
    print(f"\n  Extracting {len(FEATURE_NAMES)} features from {len(sequences)} samples...")
    X = []
    for seq in sequences:
        features = extract_features(seq)
        X.append(features)
    return np.array(X)


def train_and_evaluate():
    """Full training pipeline."""
    print("=" * 65)
    print("       GESTURE RECOGNITION MODEL TRAINER — Phase 4")
    print("=" * 65)

    # Load data
    labels, sequences = load_data()
    print(f"\n  Loaded {len(labels)} samples from {CSV_PATH.name}")

    # Check counts
    samples_per_class = check_sample_counts(labels)

    # Build feature matrix
    X = build_feature_matrix(sequences)
    y = np.array(labels)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\n  Train set: {len(X_train)} samples")
    print(f"  Test set:  {len(X_test)} samples")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # --- MODEL A: Random Forest ---
    print("\n" + "-" * 65)
    print("  MODEL A: Random Forest")
    print("-" * 65)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train_scaled, y_train)

    rf_train_acc = accuracy_score(y_train, rf.predict(X_train_scaled))
    rf_test_acc = accuracy_score(y_test, rf.predict(X_test_scaled))
    rf_pred = rf.predict(X_test_scaled)

    print(f"  Training accuracy: {rf_train_acc:.4f}")
    print(f"  Test accuracy:     {rf_test_acc:.4f}")
    print(f"\n  Confusion Matrix:")
    _print_confusion_matrix(y_test, rf_pred)
    print(f"\n  Classification Report:")
    print(classification_report(y_test, rf_pred, zero_division=0))

    # --- MODEL B: SVM ---
    print("-" * 65)
    print("  MODEL B: SVM (RBF kernel)")
    print("-" * 65)
    svm = SVC(kernel='rbf', C=1.0, probability=True, random_state=42)
    svm.fit(X_train_scaled, y_train)

    svm_train_acc = accuracy_score(y_train, svm.predict(X_train_scaled))
    svm_test_acc = accuracy_score(y_test, svm.predict(X_test_scaled))
    svm_pred = svm.predict(X_test_scaled)

    print(f"  Training accuracy: {svm_train_acc:.4f}")
    print(f"  Test accuracy:     {svm_test_acc:.4f}")
    print(f"\n  Confusion Matrix:")
    _print_confusion_matrix(y_test, svm_pred)
    print(f"\n  Classification Report:")
    print(classification_report(y_test, svm_pred, zero_division=0))

    # --- Select better model ---
    print("=" * 65)
    if rf_test_acc >= svm_test_acc:
        best_model = rf
        best_name = "RandomForest"
        best_acc = rf_test_acc
        print(f"  WINNER: Random Forest (test acc: {rf_test_acc:.4f} vs SVM: {svm_test_acc:.4f})")
    else:
        best_model = svm
        best_name = "SVM"
        best_acc = svm_test_acc
        print(f"  WINNER: SVM (test acc: {svm_test_acc:.4f} vs RF: {rf_test_acc:.4f})")

    # Save model, scaler, and info
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(best_model, MODEL_PATH)
    print(f"  Model saved to: {MODEL_PATH}")

    joblib.dump(scaler, SCALER_PATH)
    print(f"  Scaler saved to: {SCALER_PATH}")

    model_info = {
        "model_type": best_name,
        "test_accuracy": round(best_acc, 4),
        "trained_on": datetime.now().isoformat(),
        "samples_per_class": samples_per_class,
        "feature_names": FEATURE_NAMES,
        "total_samples": len(labels),
        "train_size": len(X_train),
        "test_size": len(X_test)
    }

    with open(INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(model_info, f, indent=4)
    print(f"  Model info saved to: {INFO_PATH}")

    print("\n  Model saved. Ready for Phase 5.")
    print("=" * 65)


def _print_confusion_matrix(y_true, y_pred):
    """Print confusion matrix as a formatted ASCII table."""
    labels_sorted = sorted(set(y_true) | set(y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted)

    # Header
    max_label_len = max(len(l) for l in labels_sorted)
    col_width = max(5, max_label_len)

    header = " " * (max_label_len + 4)
    for label in labels_sorted:
        header += f"{label:>{col_width}s} "
    print(f"    {header}")
    print(f"    {' ' * (max_label_len + 4)}{'-' * ((col_width + 1) * len(labels_sorted))}")

    for i, label in enumerate(labels_sorted):
        row_str = f"    {label:>{max_label_len}s} |  "
        for j in range(len(labels_sorted)):
            row_str += f"{cm[i][j]:>{col_width}d} "
        print(row_str)


if __name__ == "__main__":
    train_and_evaluate()
