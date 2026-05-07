// Detector interface
class Detector:
    """Base class for all regime detectors"""
    def detect_regime(self, data: pd.DataFrame) -> RegimeLabel:
        """Detect regime based on input data"""
        raise NotImplementedError("Subclasses must implement this method")

// Simple volatility-based detector
class VolatilityDetector(Detector):
    """Detects regime based on rolling volatility"""
    def __init__(self, window: int = 20):
        self.window = window

    def detect_regime(self, data: pd.DataFrame) -> RegimeLabel:
        """Calculate rolling volatility and classify regime"""
        returns = data['returns'].rolling(window=self.window).std()
        avg_volatility = returns.mean()
        if avg_volatility > 0.02:
            return RegimeLabel.HIGH_VOLATILITY
        elif avg_volatility > 0.01:
            return RegimeLabel.LOW_VOLATILITY
        else:
            return RegimeLabel.RANGING