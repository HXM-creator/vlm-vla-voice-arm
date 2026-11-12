"""六状态状态机。"""
from __future__ import annotations

from enum import Enum, auto


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


class InvalidTransition(RuntimeError):
    pass


class StateMachine:
    def __init__(self, initial: State = State.IDLE):
        self._state = initial

    @property
    def state(self) -> State:
        return self._state

    def can_transition(self, nxt: State) -> bool:
        return nxt in TRANSITIONS[self._state]

    def transition(self, nxt: State) -> State:
        if not self.can_transition(nxt):
            raise InvalidTransition(f"{self._state.name} -> {nxt.name} is not allowed")
        self._state = nxt
        return self._state
