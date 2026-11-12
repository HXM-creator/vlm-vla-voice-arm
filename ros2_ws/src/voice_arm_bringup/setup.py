from glob import glob

from setuptools import setup

package_name = "voice_arm_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="何佳俊",
    maintainer_email="hxm@example.com",
    description="ROS2 节点与 launch",
    license="MIT",
    entry_points={
        "console_scripts": [
            "audio_node = voice_arm_bringup.audio_node:main",
            "vlm_node = voice_arm_bringup.vlm_node:main",
            "policy_node = voice_arm_bringup.policy_node:main",
            "robot_node = voice_arm_bringup.robot_node:main",
            "orchestrator_node = voice_arm_bringup.orchestrator_node:main",
        ],
    },
)
