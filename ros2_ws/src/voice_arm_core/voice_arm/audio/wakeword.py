"""唤醒词检测（openWakeWord）。"""
from __future__ import annotations


class WakeWordDetector:
    def __init__(self, model: str = "alexa", threshold: float = 0.5):
        self.model = model
        self.threshold = threshold
        self._ready = False

    def load(self) -> bool:
        try:
            import openwakeword  # noqa: F401
            self._ready = True
        except ImportError:
            self._ready = False
        return self._ready

    def wait(self) -> bool:
        raise NotImplementedError("接入 openWakeWord 音频流后实现")
