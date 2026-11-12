from setuptools import find_packages, setup

package_name = "voice_arm_core"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools", "numpy", "pyyaml"],
    zip_safe=True,
    maintainer="何佳俊",
    maintainer_email="hxm@example.com",
    description="纯 Python 核心库，不依赖 ROS2",
    license="MIT",
    tests_require=["pytest"],
    entry_points={"console_scripts": []},
)
