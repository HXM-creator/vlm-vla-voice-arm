"""中文语音识别（FunASR / SenseVoice）。

用法：
    asr = ASR()
    asr.load()
    text = asr.transcribe(audio_int16)   # np.ndarray 或 wav 路径
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np

from .errors import AudioDependencyError

log = logging.getLogger(__name__)

DEFAULT_MODEL = "iic/SenseVoiceSmall"


class ASR:
    """FunASR 封装，默认加载 SenseVoice-small。"""

    def __init__(self, model: str = DEFAULT_MODEL, language: str = "zh",
                 sample_rate: int = 16000):
        self.model_name = model
        self.language = language
        self.sample_rate = sample_rate
        self._model = None

    @staticmethod
    def available() -> bool:
        try:
            import funasr  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self) -> bool:
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise AudioDependencyError(
                "funasr",
                "pip install 'funasr>=1.1'",
                "中文语音识别",
            ) from exc

        self._model = AutoModel(
            model=self.model_name,
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_update=True,
        )
        log.info("asr model loaded: %s", self.model_name)
        return True

    def transcribe(self, audio: np.ndarray | str | Path) -> str:
        """识别一段音频，返回中文文本。

        Args:
            audio: int16 单声道 ndarray，或 wav 文件路径
        """
        if self._model is None:
            raise RuntimeError("请先调用 load()")

        path = Path(audio) if isinstance(audio, (str, Path)) else self._write_wav(audio)
        result = self._model.generate(
            input=str(path),
            language=self.language,
            use_itn=True,
            batch_size_s=60,
        )
        if not result:
            return ""
        # FunASR 返回 [{"text": "..."}]，新版本可能带 <|zh|> 等标记
        text = result[0].get("text", "") if isinstance(result[0], dict) else str(result[0])
        return _clean(text)

    def _write_wav(self, audio: np.ndarray) -> Path:
        """把 int16 ndarray 写成临时 wav，FunASR 需要文件路径。"""
        try:
            import soundfile as sf
        except ImportError as exc:
            raise AudioDependencyError(
                "soundfile",
                "pip install 'soundfile>=0.12'",
                "音频转 wav",
            ) from exc

        audio = np.asarray(audio, dtype=np.int16)
        tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
        sf.write(tmp, audio, self.sample_rate, subtype="PCM_16")
        return tmp


def _clean(text: str) -> str:
    """去掉 SenseVoice 输出的语言/情感标记。"""
    import re

    return re.sub(r"<\|[^|]+\|>", "", text).strip()
