"""
Real-Time Gesture Recogniser — Phase 4.

Maintains a rolling buffer of filtered RSSI readings.
Every 0.5s: extract features → predict gesture → triple-confirm → fire event.

Usage:
    Integrated via main.py, or test standalone:
    python -m gesture_engine.gesture_recogniser
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import joblib

from .feature_extractor import extract_features

# Paths
ROOT_DIR = Path(__file__).parent.parent
MODEL_PATH = ROOT_DIR / "models" / "gesture_model.pkl"
SCALER_PATH = ROOT_DIR / "models" / "scaler.pkl"
GESTURE_LOG = ROOT_DIR / "logs" / "gesture_events.jsonl"

# Recognition parameters
BUFFER_SIZE = 8              # 8 readings per window
EVAL_INTERVAL = 0.5          # evaluate every 0.5 seconds
CONFIDENCE_THRESHOLD = 0.70  # 70% minimum
CONSECUTIVE_REQUIRED = 3     # 3 matching predictions to confirm
COOLDOWN_SECONDS = 2.0       # minimum time between gesture firings

# Gesture display indicators
GESTURE_INDICATORS = {
    "ROTATION":        "🔄 ROTATION detected",
    "SLOW_DEPARTURE":  "🚶 SLOW_DEPARTURE detected",
    "DOUBLE_APPROACH": "✋ DOUBLE_APPROACH detected",
    "IDLE":            "💤 IDLE detected"
}

GESTURE_ACTIONS = {
    "ROTATION":        "Volume control",
    "SLOW_DEPARTURE":  "Lock screen",
    "DOUBLE_APPROACH": "Wake/confirm",
    "IDLE":            "No action"
}


class GestureRecogniser:
    """
    Real-time gesture recognition from a rolling buffer of filtered RSSI readings.
    """
    def __init__(self):
        self.model = None
        self.scaler = None
        self.model_loaded = False

        # Rolling RSSI buffer
        self.rssi_buffer = []

        # Confirmation tracking
        self._consecutive_predictions = []
        self._last_fire_time = 0.0

        # Latest confirmed gesture (for display/export)
        self._latest_gesture = None

        # Running flag
        self.running = False

        # Ensure log directory exists
        GESTURE_LOG.parent.mkdir(parents=True, exist_ok=True)

    def load_model(self) -> bool:
        """Load the trained model and scaler from disk."""
        if not MODEL_PATH.exists():
            print("[WARNING] Gesture model not found. Gesture recognition disabled.")
            print(f"  Expected: {MODEL_PATH}")
            print("  Train a model first: python -m gesture_engine.train_model")
            return False
        if not SCALER_PATH.exists():
            print("[WARNING] Scaler not found. Gesture recognition disabled.")
            return False

        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.model_loaded = True
            print(f"[INFO] Gesture model loaded from {MODEL_PATH.name}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load gesture model: {e}")
            return False

    def add_reading(self, filtered_rssi: float):
        """Add a new filtered RSSI reading to the rolling buffer."""
        if filtered_rssi is None or filtered_rssi == -127.0:
            return
        self.rssi_buffer.append(filtered_rssi)
        if len(self.rssi_buffer) > BUFFER_SIZE:
            self.rssi_buffer.pop(0)

    def predict_gesture(self) -> tuple:
        """
        Predict gesture from current buffer.
        Returns (gesture_label, confidence) or (None, 0.0) if buffer not full.
        """
        if not self.model_loaded or len(self.rssi_buffer) < BUFFER_SIZE:
            return None, 0.0

        features = extract_features(self.rssi_buffer)
        features_scaled = self.scaler.transform([features])

        # Get prediction and probability
        prediction = self.model.predict(features_scaled)[0]
        probabilities = self.model.predict_proba(features_scaled)[0]
        confidence = float(np.max(probabilities))

        return prediction, confidence

    def evaluate(self) -> dict:
        """
        Run one evaluation cycle:
        1. Predict gesture from current buffer
        2. Check confidence threshold
        3. Track consecutive predictions
        4. Fire event if triple-confirmed and cooldown elapsed

        Returns confirmed gesture dict if fired, else None.
        """
        prediction, confidence = self.predict_gesture()

        if prediction is None:
            return None

        # Check confidence threshold
        if confidence < CONFIDENCE_THRESHOLD:
            self._consecutive_predictions.clear()
            return None

        # Skip IDLE for confirmation tracking — it's a background state
        # We still track it but never "fire" it as an event
        if prediction == "IDLE":
            self._consecutive_predictions.clear()
            return None

        # Track consecutive matching predictions
        if self._consecutive_predictions and self._consecutive_predictions[-1] == prediction:
            self._consecutive_predictions.append(prediction)
        else:
            self._consecutive_predictions = [prediction]

        # Check if we have enough consecutive confirmations
        if len(self._consecutive_predictions) < CONSECUTIVE_REQUIRED:
            return None

        # Check cooldown
        now = time.time()
        if now - self._last_fire_time < COOLDOWN_SECONDS:
            return None

        # FIRE the gesture
        self._last_fire_time = now
        self._consecutive_predictions.clear()

        gesture_event = {
            "gesture": prediction,
            "confidence": round(confidence * 100.0, 1),
            "timestamp": datetime.now().isoformat(),
            "rssi_sequence": list(self.rssi_buffer)
        }

        self._latest_gesture = gesture_event

        # Log to file
        try:
            with open(GESTURE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(gesture_event) + "\n")
        except Exception as e:
            print(f"[ERROR] Failed to write gesture event: {e}")

        # Print to terminal
        indicator = GESTURE_INDICATORS.get(prediction, prediction)
        action = GESTURE_ACTIONS.get(prediction, "Unknown")
        print(f"\n  {indicator} (conf: {gesture_event['confidence']:.1f}%) → {action}")

        return gesture_event

    def get_latest_gesture(self) -> dict:
        """Returns the latest confirmed gesture event, or None."""
        return self._latest_gesture

    async def run(self, filtered_log_path: Path):
        """
        Async loop: tail the filtered log and evaluate every EVAL_INTERVAL seconds.
        """
        self.running = True

        if not self.model_loaded:
            print("[INFO] Gesture recogniser running without model. Waiting for model...")
            # Keep running but do nothing until model is loaded
            while self.running:
                await asyncio.sleep(1.0)
            return

        # Wait for log file
        while self.running and not filtered_log_path.exists():
            await asyncio.sleep(0.5)

        if not self.running:
            return

        # Tail the filtered log for new readings
        with open(filtered_log_path, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # Go to end
            last_eval_time = time.time()

            while self.running:
                line = f.readline()
                if line:
                    try:
                        data = json.loads(line.strip())
                        filtered = data.get("filtered_rssi")
                        if filtered is not None:
                            self.add_reading(filtered)
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Evaluate at the specified interval
                now = time.time()
                if now - last_eval_time >= EVAL_INTERVAL:
                    self.evaluate()
                    last_eval_time = now

                if not line:
                    await asyncio.sleep(0.05)

    def stop(self):
        """Stop the recogniser loop."""
        self.running = False


# Module-level singleton for easy access
_recogniser = None


def init_recogniser() -> GestureRecogniser:
    """Initialize and return the global gesture recogniser."""
    global _recogniser
    _recogniser = GestureRecogniser()
    _recogniser.load_model()
    return _recogniser


def get_latest_gesture() -> dict:
    """Get the latest confirmed gesture from the global recogniser."""
    global _recogniser
    if _recogniser is None:
        return None
    return _recogniser.get_latest_gesture()


if __name__ == "__main__":
    print("Gesture Recogniser module loaded successfully.")
    print(f"  Model path: {MODEL_PATH}")
    print(f"  Model exists: {MODEL_PATH.exists()}")
    print(f"  Scaler exists: {SCALER_PATH.exists()}")
    rec = GestureRecogniser()
    loaded = rec.load_model()
    if loaded:
        # Quick test with a sample buffer
        test_buffer = [-58, -60, -57, -61, -59, -58, -62, -60]
        rec.rssi_buffer = test_buffer
        pred, conf = rec.predict_gesture()
        print(f"  Test prediction: {pred} (confidence: {conf:.2%})")
