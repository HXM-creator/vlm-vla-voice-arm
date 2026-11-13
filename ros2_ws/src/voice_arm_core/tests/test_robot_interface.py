import numpy as np
import pytest

from voice_arm.robot.interface import RobotInterface
from voice_arm.robot.sim import SimRobot


def test_sim_implements_interface():
    assert issubclass(SimRobot, RobotInterface)
    robot = SimRobot()
    assert robot.connect() is True


def test_joint_roundtrip():
    robot = SimRobot()
    robot.connect()
    q = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)
    robot.set_joint_positions(q)
    np.testing.assert_allclose(robot.get_joint_positions(), q)


def test_joint_shape_check():
    robot = SimRobot()
    with pytest.raises(ValueError):
        robot.set_joint_positions(np.zeros(3, dtype=np.float32))


def test_gripper_clip():
    robot = SimRobot()
    robot.set_gripper(1.5)
    assert robot.get_gripper_state() == 1.0


def test_default_two_cameras():
    frames = SimRobot().get_frames()
    assert set(frames) == {"front", "wrist"}
    assert frames["front"].ndim == 3


def test_single_camera_config():
    frames = SimRobot(cameras=("front",)).get_frames()
    assert set(frames) == {"front"}


def test_missing_xml_falls_back():
    """模型文件不存在时不应抛异常，而是回退到合成图像。"""
    robot = SimRobot(xml_path="/nonexistent/scene.xml")
    frames = robot.get_frames()
    assert set(frames) == {"front", "wrist"}


def test_deg_to_rad_guard():
    """度/弧度混用时必须抛错，避免机械臂大幅甩动。"""
    from voice_arm.robot.real import RealRobot

    ok = RealRobot._deg_to_rad(np.array([10, 20, 30, 40, 50, 60], dtype=np.float32))
    assert ok.shape == (6,)
    assert abs(ok[0] - np.deg2rad(10)) < 1e-6

    with pytest.raises(ValueError):
        RealRobot._deg_to_rad(np.array([400, 20, 30, 40, 50, 60], dtype=np.float32))
