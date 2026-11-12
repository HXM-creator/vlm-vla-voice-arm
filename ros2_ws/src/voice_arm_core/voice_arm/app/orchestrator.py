"""主循环：串联语音、VLM、策略与语音反馈。

当前为骨架实现，使用 SimRobot 跑通链路；接入真实模型后替换对应组件。
"""
from __future__ import annotations

import argparse
import logging

from voice_arm.app.state_machine import State, StateMachine
from voice_arm.policy.runner import PolicyRunner
from voice_arm.robot.sim import SimRobot
from voice_arm.utils.config import load_config
from voice_arm.utils.logging import setup_logging

log = logging.getLogger(__name__)


def build_robot(cfg: dict):
    backend = cfg.get("robot", {}).get("backend", "sim")
    if backend == "sim":
        return SimRobot(dof=cfg["robot"]["dof"], image_size=tuple(cfg["robot"]["image_size"]))
    from voice_arm.robot.real import RealRobot
    return RealRobot(port=cfg["robot"].get("port", "/dev/ttyACM0"))


def run(config_path: str) -> None:
    cfg = load_config(config_path)
    setup_logging()
    sm = StateMachine()
    robot = build_robot(cfg)
    robot.connect()
    policy = PolicyRunner(action_chunk=cfg["policy"]["action_chunk"], dof=cfg["robot"]["dof"])

    try:
        sm.transition(State.LISTENING)
        log.info("state=%s（此处接入唤醒词与 ASR）", sm.state.name)
        sm.transition(State.THINKING)
        log.info("state=%s（此处接入 VLM 解析）", sm.state.name)
        sm.transition(State.EXECUTING)
        frames = robot.get_frames()
        actions = policy.predict(frames, instruction="placeholder")
        log.info("state=%s action_chunk=%s", sm.state.name, actions.shape)
        robot.set_joint_positions(actions[0])
        sm.transition(State.FEEDBACK)
        log.info("state=%s（此处接入 TTS 播报）", sm.state.name)
        sm.transition(State.IDLE)
    finally:
        robot.disconnect()
        log.info("done, final state=%s", sm.state.name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/sim.yaml")
    args = ap.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
