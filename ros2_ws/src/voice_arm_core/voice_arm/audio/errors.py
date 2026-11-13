"""音频模块的异常类型，便于上层区分「没装依赖」与「运行失败」。"""
from __future__ import annotations


class AudioError(RuntimeError):
    """音频模块基础异常。"""


class AudioDependencyError(AudioError):
    """缺少可选依赖。消息里直接给出安装命令。"""

    def __init__(self, package: str, install: str, purpose: str):
        super().__init__(f"{purpose} 需要 {package}，安装：{install}")
        self.package = package
        self.install = install
