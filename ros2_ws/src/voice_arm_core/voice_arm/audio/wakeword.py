"""唤醒词检测（openWakeWord）。

用法：
    det = WakeWordDetector()
    det.load()
    while True:
        if det.read_and_predict():   # 阻塞读一帧
            break
"""
from __future__ import annotations

import logging

import numpy as np

from .errors import AudioDependencyError

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280  # 80 ms @16k，openWakeWord 推荐的帧长


class WakeWordDetector:
    """openWakeWord 封装。

    Args:
        model: 预置模型名，如 "hey_jarvis" / "alexa"
        threshold: 触发阈值，0~1
        sample_rate: 采样率，固定 16000
    """

    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5,
                 sample_rate: int = SAMPLE_RATE):
        self.model_name = model
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._model = None
        self._stream = None

    @staticmethod
    def available() -> bool:
        try:
            import openwakeword  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self) -> bool:
        """加载模型。缺依赖时抛 AudioDependencyError。"""
        try:
            from openwakeword.model import Model
        except ImportError as exc:
            raise AudioDependencyError(
                "openwakeword",
                "pip install 'openwakeword>=0.6'",
                "唤醒词检测",
            ) from exc

        self._model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        log.info("wakeword model loaded: %s", self.model_name)
        return True

    def predict(self, frame: np.ndarray) -> float:
        """输入一帧 int16 音频，返回最高唤醒分数。"""
        if self._model is None:
            raise RuntimeError("请先调用 load()")
        scores = self._model.predict(frame)
        return float(max(scores.values())) if scores else 0.0

    def read_and_predict(self, timeout_s: float | None = None) -> bool:
        """从麦克风读一帧并判断是否唤醒。timeout_s 为 None 时一直等。"""
        import time

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDependencyError(
                "sounddevice",
                "pip install 'sounddevice>=0.4'",
                "麦克风采集",
            ) from exc

        if self._stream is None:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate, channels=1, dtype="int16",
                blocksize=FRAME_SAMPLES,
            )
            self._stream.start()

        if timeout_s is not None:
            deadline = time.monotonic() + timeout_s
        else:
            deadline = None

        while True:
            if deadline is not None and time.monotonic() > deadline:
                return False
            frame, _ = self._stream.read(FRAME_SAMPLES)
            if self.predict(frame[:, 0]) >= self.threshold:
                return True

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
