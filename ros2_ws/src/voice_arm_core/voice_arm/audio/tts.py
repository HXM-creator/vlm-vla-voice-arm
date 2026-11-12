"""语音合成（edge-tts）。"""
from __future__ import annotations


class TTS:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    async def speak(self, text: str) -> None:
        raise NotImplementedError("接入 edge-tts 后实现")
