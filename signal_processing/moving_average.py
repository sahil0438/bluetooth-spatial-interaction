class MovingAverage:
    """
    A 1D Moving Average filter implementation for smoothing real-time RSSI streams.
    """
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history = []

    def update(self, val: float) -> float:
        """
        Appends a new value to the history and returns the updated moving average.
        """
        self.history.append(val)
        if len(self.history) > self.window_size:
            self.history.pop(0)
            
        # Return average of current history
        return sum(self.history) / len(self.history)

    def reset(self):
        """Clears the filter history."""
        self.history.clear()

if __name__ == "__main__":
    # Test vector specified in requirements
    raw_samples = [-62, -58, -65, -70, -60, -55, -68, -72, -64, -58]
    
    ma_filter = MovingAverage(window_size=5)
    
    print("Moving Average Test (Window Size = 5):")
    print(f"{'Index':<6} | {'Raw RSSI':<10} | {'Smoothed RSSI':<15}")
    print("-" * 38)
    
    for i, raw in enumerate(raw_samples):
        smoothed = ma_filter.update(raw)
        print(f"{i:<6} | {raw:<10} | {smoothed:<15.2f}")
