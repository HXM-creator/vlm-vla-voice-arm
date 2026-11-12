"""中文语音识别（FunASR SenseVoice-small）。"""
from __future__ import annotations


class ASR:
    def __init__(self, model: str = "sensevoice-small", language: str = "zh"):
        self.model = model
        self.language = language

    def transcribe(self, audio: bytes) -> str:
        raise NotImplementedError("接入 FunASR 后实现")
