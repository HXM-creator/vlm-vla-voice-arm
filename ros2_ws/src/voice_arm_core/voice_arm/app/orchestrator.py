"""主循环：三线程协调语音、VLM、策略与硬件。

线程模型：
- 主线程：状态机 tick 与状态切换，不阻塞
- VLM 线程：从指令队列取文本，调用视觉语言模型，结果入命令队列
- 执行线程：固定 30 Hz，仅在 EXECUTING 状态读帧、推理、下发

关键约束：VLM 云端调用 2–5 秒，绝不能出现在 30 Hz 的执行路径上。
"""
from __future__ import annotations

import argparse
import logging
import queue
import threading
import time
from typing import Any, Callable

import numpy as np

from voice_arm.app.state_machine import State, StateMachine
from voice_arm.policy.runner import PolicyRunner
from voice_arm.robot.sim import SimRobot
from voice_arm.utils.config import load_config
from voice_arm.utils.logging import setup_logging

log = logging.getLogger(__name__)

# 执行线程固定频率；与 configs 里的 control_hz 解耦
EXEC_HZ = 30.0

# FEEDBACK 最短驻留时间：语音播报需要出口，不能在同一轮里直接回 IDLE
FEEDBACK_MIN_S = 0.2


class Orchestrator:
    """把语音、VLM、策略、硬件串起来的调度器。

    Args:
        robot: RobotInterface 实现
        policy: PolicyRunner
        cfg: 配置字典
        vlm: 可选，需提供 parse(instruction, image_b64) -> Command
        tts: 可选，需提供 speak(text) -> None
        clock: 单调时钟，测试可注入
    """

    def __init__(self, robot, policy, cfg: dict[str, Any],
                 vlm=None, tts=None, clock: Callable[[], float] = time.monotonic):
        self.robot = robot
        self.policy = policy
        self.cfg = cfg
        self.vlm = vlm
        self.tts = tts

        self.sm = StateMachine(clock=clock)
        self._stop = threading.Event()
        # 外部提交 -> 主线程消费；主线程 -> VLM 线程用独立的内部队列，
        # 避免两个线程抢同一个 Queue 导致文本被一方取走后另一方永远等不到
        self._instruction_q: queue.Queue[str] = queue.Queue()
        self._vlm_in_q: queue.Queue[str] = queue.Queue()
        self._command_q: queue.Queue[Any] = queue.Queue()

        self._threads: list[threading.Thread] = []
        self._last_exec = 0.0
        self._exec_steps_left = 0

    # ---------- 对外接口 ----------
    def submit_instruction(self, text: str) -> None:
        """语音识别完成后调用；主线程收到后进入 THINKING。"""
        self._instruction_q.put(text)

    def start(self) -> None:
        self.robot.connect()
        self._threads = [
            threading.Thread(target=self._vlm_worker, name="vlm", daemon=True),
            threading.Thread(target=self._exec_worker, name="exec", daemon=True),
        ]
        for t in self._threads:
            t.start()
        log.info("orchestrator started")

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self.robot.disconnect()
        log.info("orchestrator stopped")

    # ---------- 主循环 ----------
    def run_once(self) -> State:
        """推进一次状态机。主循环应定期调用。"""
        if self.sm.tick():
            log.warning("state timeout, reset to IDLE")

        # FEEDBACK 至少驻留 FEEDBACK_MIN_S，保证播报有出口且外部能观察到该状态
        if self.sm.state is State.FEEDBACK and self.sm.elapsed() >= FEEDBACK_MIN_S:
            self.sm.transition(State.IDLE)

        if self.sm.state is State.IDLE and not self._instruction_q.empty():
            self.sm.transition(State.LISTENING)
            text = self._instruction_q.get_nowait()
            log.info("instruction: %s", text)
            self.sm.transition(State.THINKING)
            # 转交给 VLM 线程；主线程不再碰这条文本
            self._vlm_in_q.put(text)

        if self.sm.state is State.THINKING and not self._command_q.empty():
            cmd = self._command_q.get_nowait()
            if getattr(cmd, "need_clarify", False) or not getattr(cmd, "target_present", True):
                self._speak(getattr(cmd, "clarify_question", None) or getattr(cmd, "reply", ""))
                self.sm.transition(State.CONFIRMING)
            else:
                self._speak(getattr(cmd, "reply", ""))
                self._exec_steps_left = int(self.cfg.get("policy", {}).get("action_chunk", 16))
                self.sm.transition(State.EXECUTING)

        if self.sm.state is State.CONFIRMING:
            # 等待使用者重述；超时由 tick 处理
            pass

        if self.sm.state is State.EXECUTING and self._exec_steps_left <= 0:
            self.sm.transition(State.FEEDBACK)
            self._speak("完成了")

        return self.sm.state

    # ---------- VLM 线程 ----------
    def _vlm_worker(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._vlm_in_q.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                frames = self.robot.get_frames()
                image = frames.get("front")
                cmd = self._call_vlm(text, image)
                self._command_q.put(cmd)
            except Exception as exc:  # noqa: BLE001
                log.error("vlm failed: %s", exc)
                self._command_q.put(_fallback_command(text))

    def _call_vlm(self, text: str, image: np.ndarray | None):
        if self.vlm is None:
            return _fallback_command(text)
        b64 = _encode_jpeg(image)
        return self.vlm.parse(text, b64)

    # ---------- 执行线程 ----------
    def _exec_worker(self) -> None:
        period = 1.0 / EXEC_HZ
        while not self._stop.is_set():
            loop_start = time.monotonic()
            try:
                if self.sm.state is State.EXECUTING and self._exec_steps_left > 0:
                    frames = self.robot.get_frames()
                    actions = self.policy.predict(frames, instruction="")
                    self.robot.set_joint_positions(actions[0])
                    self._exec_steps_left -= 1
            except Exception as exc:  # noqa: BLE001
                log.error("exec failed: %s", exc)
                self._exec_steps_left = 0

            rest = period - (time.monotonic() - loop_start)
            if rest > 0:
                time.sleep(rest)

    # ---------- 语音 ----------
    def _speak(self, text: str) -> None:
        if text:
            log.info("speak: %s", text)
            if self.tts is not None:
                try:
                    self.tts.speak(text)
                except Exception as exc:  # noqa: BLE001
                    log.warning("tts failed: %s", exc)


def _fallback_command(text: str):
    """无 VLM 时的占位指令，保证链路可跑。"""
    from voice_arm.vlm.schema import Action, Command, Destination, Target

    return Command(
        action=Action.PICK_PLACE,
        target=Target(color="green", shape="cube", description=text),
        destination=Destination(region="right"),
        reply="好的，我去拿绿色的方块",
        confidence=0.5,
        target_present=True,
    )


def build_robot(cfg: dict):
    backend = cfg.get("robot", {}).get("backend", "sim")
    if backend == "sim":
        xml = cfg.get("robot", {}).get("sim_xml") or None
        return SimRobot(
            dof=cfg["robot"]["dof"],
            image_size=tuple(cfg["robot"]["image_size"]),
            xml_path=xml,
            cameras=tuple(cfg["robot"].get("cameras", ("front", "wrist"))),
        )
    from voice_arm.robot.real import RealRobot

    return RealRobot(
        port=cfg["robot"].get("port", "/dev/ttyACM0"),
        cameras=tuple(cfg["robot"].get("cameras", ("front", "wrist"))),
        camera_index=cfg["robot"].get("camera_index"),
    )


def run(config_path: str, duration_s: float | None = None) -> None:
    cfg = load_config(config_path)
    setup_logging()
    robot = build_robot(cfg)
    policy = PolicyRunner(
        checkpoint=cfg.get("policy", {}).get("checkpoint") or None,
        action_chunk=cfg.get("policy", {}).get("action_chunk", 16),
        dof=cfg.get("robot", {}).get("dof", 6),
    )
    orch = Orchestrator(robot, policy, cfg)
    orch.start()
    try:
        if duration_s:
            orch.submit_instruction("把绿色的方块放到右边")
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline:
                state = orch.run_once()
                log.info("state=%s", state.name)
                time.sleep(1.0 / EXEC_HZ)
        else:
            while True:
                orch.run_once()
                time.sleep(1.0 / EXEC_HZ)
    except KeyboardInterrupt:
        pass
    finally:
        orch.stop()


def main() -> None:
    ap = argparse.ArgumentParser(description="语音控制机械臂主循环")
    ap.add_argument("--config", default="ros2_ws/src/voice_arm_bringup/config/params.yaml")
    ap.add_argument("--duration", type=float, default=None, help="运行秒数，默认一直跑")
    args = ap.parse_args()
    run(args.config, args.duration)


if __name__ == "__main__":
    main()
