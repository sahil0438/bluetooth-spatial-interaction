import numpy as np

class KalmanFilter1D:
    """
    A 1D Kalman Filter implemented in pure NumPy for smoothing BLE RSSI signals.
    """
    def __init__(self, q: float = 0.008, r: float = 2.0, x0: float = -62.0, p0: float = 1.0):
        # Process noise covariance (Q) - how much the actual value fluctuates
        self.q = np.float64(q)
        # Measurement noise covariance (R) - how much the sensor measurement fluctuates
        self.r = np.float64(r)
        
        # State estimate (x)
        self.x = np.float64(x0)
        # Estimate covariance (P) - error of estimate
        self.p = np.float64(p0)

    def update(self, measurement: float) -> float:
        """
        Runs one step of the Kalman Filter: Predict and Correct.
        """
        # --- Predict Phase ---
        # State extrapolation (constant dynamic model: x_k = x_{k-1})
        # Covariance extrapolation (P_k = P_{k-1} + Q)
        p_predict = self.p + self.q

        # --- Correct Phase ---
        # Kalman Gain (K = P_predict / (P_predict + R))
        gain = p_predict / (p_predict + self.r)
        
        # Update estimate (x = x_predict + K * (measurement - x_predict))
        self.x = self.x + gain * (np.float64(measurement) - self.x)
        
        # Update estimate covariance (P = (1 - K) * P_predict)
        self.p = (np.float64(1.0) - gain) * p_predict

        return float(self.x)

    def reset(self, x0: float = -62.0, p0: float = 1.0):
        """Resets the state of the Kalman Filter."""
        self.x = np.float64(x0)
        self.p = np.float64(p0)

if __name__ == "__main__":
    from moving_average import MovingAverage
    
    # Test vector specified in requirements
    raw_samples = [-62, -58, -65, -70, -60, -55, -68, -72, -64, -58]
    
    ma_filter = MovingAverage(window_size=5)
    kf_filter = KalmanFilter1D(q=0.008, r=2.0, x0=-62.0, p0=1.0)
    
    print("Filter Cascade Test (Raw -> Moving Average -> Kalman):")
    print(f"{'Index':<6} | {'Raw RSSI':<10} | {'Moving Avg':<12} | {'Kalman Output':<15}")
    print("-" * 52)
    
    for i, raw in enumerate(raw_samples):
        smoothed = ma_filter.update(raw)
        kalman = kf_filter.update(smoothed)
        print(f"{i:<6} | {raw:<10} | {smoothed:<12.2f} | {kalman:<15.4f}")
