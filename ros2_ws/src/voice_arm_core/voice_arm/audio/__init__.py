"""语音链路：唤醒词、语音识别、语音合成。

三个模块都采用延迟导入：未安装依赖时仍可 import 本包，
只有真正调用相关功能时才抛出 AudioDependencyError。
"""
from .asr import ASR
from .errors import AudioDependencyError, AudioError
from .tts import TTS
from .wakeword import WakeWordDetector

__all__ = ["ASR", "TTS", "WakeWordDetector", "AudioError", "AudioDependencyError"]
