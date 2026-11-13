"""语音合成（edge-tts）。

用法：
    tts = TTS()
    tts.speak("已经放到右边了")        # 生成并播放
    tts.save("hi.mp3", "你好")         # 只生成文件

edge-tts 是异步库，本类提供同步包装；在已有事件循环中调用请用 speak_async。
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from .errors import AudioDependencyError

log = logging.getLogger(__name__)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class TTS:
    """edge-tts 封装。"""

    def __init__(self, voice: str = DEFAULT_VOICE, rate: str = "+0%"):
        self.voice = voice
        self.rate = rate

    @staticmethod
    def available() -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    async def save_async(self, path: str | Path, text: str) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise AudioDependencyError(
                "edge-tts",
                "pip install 'edge-tts>=6.1'",
                "语音合成",
            ) from exc

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await communicate.save(str(out))
        return out

    def save(self, path: str | Path, text: str) -> Path:
        return asyncio.run(self.save_async(path, text))

    def save_temp(self, text: str) -> Path:
        tmp = Path(tempfile.mkstemp(suffix=".mp3")[1])
        return self.save(tmp, text)

    def play(self, path: str | Path) -> None:
        """播放音频文件。优先 sounddevice，缺失时回退系统播放器。"""
        path = str(path)
        try:
            import sounddevice as sd
            import soundfile as sf

            data, sr = sf.read(path, dtype="float32")
            sd.play(data, sr)
            sd.wait()
            return
        except ImportError:
            pass

        import subprocess
        import sys

        if sys.platform.startswith("linux"):
            subprocess.run(["aplay", "-q", path], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", path], check=False)
        else:  # Windows
            import os

            os.startfile(path)  # type: ignore[attr-defined]

    async def speak_async(self, text: str) -> None:
        path = await self.save_async(tempfile.mkstemp(suffix=".mp3")[1], text)
        self.play(path)

    def speak(self, text: str) -> None:
        """同步播报：合成到临时文件后播放。"""
        if not text:
            return
        try:
            path = self.save_temp(text)
            self.play(path)
        except AudioDependencyError:
            raise
        except Exception as exc:  # noqa: BLE001  播放失败不应中断主流程
            log.warning("tts play failed: %s", exc)
