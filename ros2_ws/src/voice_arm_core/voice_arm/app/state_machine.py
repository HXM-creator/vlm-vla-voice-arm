"""六状态状态机，带每状态超时。

设计要点：
- 迁移表限制合法路径，避免 LISTENING 直接跳 EXECUTING 这类越级
- 超时不受迁移表约束，任何状态超时都强制回 IDLE，保证系统可恢复
- 时间源可注入，单元测试不需要真实等待
"""
from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable


class State(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    CONFIRMING = auto()
    EXECUTING = auto()
    FEEDBACK = auto()


# 合法迁移表：状态 -> 允许的下一个状态
TRANSITIONS: dict[State, set[State]] = {
    State.IDLE: {State.LISTENING},
    State.LISTENING: {State.THINKING, State.IDLE},
    State.THINKING: {State.CONFIRMING, State.EXECUTING, State.IDLE},
    State.CONFIRMING: {State.LISTENING, State.IDLE},
    State.EXECUTING: {State.FEEDBACK, State.IDLE},
    State.FEEDBACK: {State.IDLE, State.LISTENING},
}

# 每状态超时（秒）；None 表示无限等待
TIMEOUTS: dict[State, float | None] = {
    State.IDLE: None,          # 待机可以一直等唤醒词
    State.LISTENING: 8.0,      # 等使用者说完
    State.THINKING: 15.0,      # VLM 云端调用
    State.CONFIRMING: 10.0,    # 等使用者回答追问
    State.EXECUTING: 30.0,     # 单次抓放上限
    State.FEEDBACK: 5.0,       # 播报耗时
}


class InvalidTransition(RuntimeError):
    pass


class StateMachine:
    """状态机。

    Args:
        initial: 初始状态
        clock: 单调时钟函数，默认 time.monotonic；测试时可注入假时钟
    """

    def __init__(self, initial: State = State.IDLE,
                 clock: Callable[[], float] = time.monotonic):
        self._state = initial
        self._clock = clock
        self._entered_at = clock()

    @property
    def state(self) -> State:
        return self._state

    def elapsed(self) -> float:
        """当前状态已持续时间（秒）。"""
        return self._clock() - self._entered_at

    def timeout(self, state: State | None = None) -> float | None:
        return TIMEOUTS[state or self._state]

    def can_transition(self, nxt: State) -> bool:
        return nxt in TRANSITIONS[self._state]

    def transition(self, nxt: State) -> State:
        if not self.can_transition(nxt):
            raise InvalidTransition(f"{self._state.name} -> {nxt.name} is not allowed")
        self._enter(nxt)
        return self._state

    def _enter(self, nxt: State) -> None:
        self._state = nxt
        self._entered_at = self._clock()

    def tick(self) -> bool:
        """检查超时；超时则强制回到 IDLE 并返回 True。

        超时不走迁移表：任何状态都可能因为异常卡住，必须能安全恢复。
        """
        t = TIMEOUTS[self._state]
        if t is not None and self.elapsed() > t:
            self._enter(State.IDLE)
            return True
        return False

    def __repr__(self) -> str:  # pragma: no cover
        return f"StateMachine(state={self._state.name}, elapsed={self.elapsed():.1f}s)"
