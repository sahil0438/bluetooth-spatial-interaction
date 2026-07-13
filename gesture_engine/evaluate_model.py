"""
Model Evaluation Script — Phase 4.

Loads the saved model and evaluates it in detail:
confusion matrix, per-gesture accuracy, feature importance,
and most commonly confused gesture pairs.

Usage:
    python -m gesture_engine.evaluate_model
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

from .feature_extractor import extract_features, FEATURE_NAMES

# Paths
ROOT_DIR = Path(__file__).parent.parent
CSV_PATH = ROOT_DIR / "data_collection" / "gesture_data.csv"
MODEL_PATH = ROOT_DIR / "models" / "gesture_model.pkl"
SCALER_PATH = ROOT_DIR / "models" / "scaler.pkl"
INFO_PATH = ROOT_DIR / "models" / "model_info.json"


def load_data():
    """Load gesture_data.csv and return labels and raw RSSI sequences."""
    if not CSV_PATH.exists():
        print(f"[ERROR] Data file not found: {CSV_PATH}")
        sys.exit(1)

    labels = []
    sequences = []

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
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


def evaluate():
    """Full evaluation pipeline."""
    print("=" * 65)
    print("       GESTURE MODEL EVALUATION — Phase 4")
    print("=" * 65)

    # Check model exists
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        print("[ERROR] Model or scaler not found. Train first:")
        print("  python -m gesture_engine.train_model")
        sys.exit(1)

    # Load model info
    model_info = {}
    if INFO_PATH.exists():
        with open(INFO_PATH, "r", encoding="utf-8") as f:
            model_info = json.load(f)
        print(f"\n  Model type:     {model_info.get('model_type', 'Unknown')}")
        print(f"  Trained on:     {model_info.get('trained_on', 'Unknown')}")
        print(f"  Test accuracy:  {model_info.get('test_accuracy', 'N/A')}")
        print(f"  Total samples:  {model_info.get('total_samples', 'N/A')}")

    # Load model and scaler
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    # Load data
    labels, sequences = load_data()
    print(f"\n  Loaded {len(labels)} samples for evaluation.")

    # Build features
    X = np.array([extract_features(seq) for seq in sequences])
    y = np.array(labels)

    # Use same split as training
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    X_test_scaled = scaler.transform(X_test)
    y_pred = model.predict(X_test_scaled)

    # --- Per-gesture accuracy ---
    gesture_classes = sorted(set(y_test))
    print("\n" + "-" * 65)
    print("  PER-GESTURE ACCURACY")
    print("-" * 65)
    for gesture in gesture_classes:
        mask = y_test == gesture
        correct = np.sum(y_pred[mask] == gesture)
        total = np.sum(mask)
        acc = correct / total if total > 0 else 0.0
        bar_len = int(acc * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {gesture:20s}  [{bar}]  {acc:.1%}  ({correct}/{total})")

    # --- Confusion Matrix ---
    cm = confusion_matrix(y_test, y_pred, labels=gesture_classes)
    print("\n" + "-" * 65)
    print("  CONFUSION MATRIX")
    print("-" * 65)
    max_label_len = max(len(g) for g in gesture_classes)
    col_width = max(5, max_label_len)

    # Header row
    header = " " * (max_label_len + 6)
    for g in gesture_classes:
        header += f"{g:>{col_width}s} "
    print(f"  {header}")
    print(f"  {' ' * (max_label_len + 6)}{'-' * ((col_width + 1) * len(gesture_classes))}")

    for i, gesture in enumerate(gesture_classes):
        row = f"  {gesture:>{max_label_len}s}  |  "
        for j in range(len(gesture_classes)):
            val = cm[i][j]
            if i == j:
                row += f"\033[92m{val:>{col_width}d}\033[0m "  # Green for correct
            elif val > 0:
                row += f"\033[91m{val:>{col_width}d}\033[0m "  # Red for errors
            else:
                row += f"{val:>{col_width}d} "
            
        print(row)

    # --- Most confused pairs ---
    print("\n" + "-" * 65)
    print("  MOST COMMONLY CONFUSED GESTURE PAIRS")
    print("-" * 65)
    confusion_pairs = []
    for i, g1 in enumerate(gesture_classes):
        for j, g2 in enumerate(gesture_classes):
            if i != j and cm[i][j] > 0:
                confusion_pairs.append((g1, g2, cm[i][j]))

    confusion_pairs.sort(key=lambda x: x[2], reverse=True)

    if not confusion_pairs:
        print("  No confusions detected — perfect classification!")
    else:
        for g1, g2, count in confusion_pairs[:5]:
            print(f"  {g1:20s} → misclassified as {g2:20s}  ({count} times)")

    # --- Feature Importance ---
    print("\n" + "-" * 65)
    print("  FEATURE IMPORTANCE")
    print("-" * 65)

    model_type = model_info.get("model_type", "Unknown")

    if hasattr(model, "feature_importances_"):
        # Random Forest feature importance
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        print(f"  (Random Forest — Gini importance)\n")
        for rank, idx in enumerate(indices, 1):
            bar_len = int(importances[idx] * 40)
            bar = "█" * bar_len
            print(f"  {rank:2d}. {FEATURE_NAMES[idx]:22s}  {importances[idx]:.4f}  {bar}")
    elif hasattr(model, "support_vectors_"):
        # SVM — show number of support vectors per class
        print(f"  (SVM — support vector distribution)\n")
        classes = model.classes_
        n_sv = model.n_support_
        for cls, count in zip(classes, n_sv):
            print(f"  {cls:20s}: {count} support vectors")
        print(f"\n  Total support vectors: {sum(n_sv)}")
    else:
        print("  Feature importance not available for this model type.")

    # --- Full classification report ---
    print("\n" + "-" * 65)
    print("  FULL CLASSIFICATION REPORT")
    print("-" * 65)
    print(classification_report(y_test, y_pred, zero_division=0))

    overall_acc = accuracy_score(y_test, y_pred)
    print(f"  Overall test accuracy: {overall_acc:.4f}")

    if overall_acc >= 0.80:
        print("  Status: GOOD — model is ready for real-time use.")
    else:
        print("  Status: NEEDS IMPROVEMENT — collect more/better training data.")

    print("=" * 65)


if __name__ == "__main__":
    evaluate()
