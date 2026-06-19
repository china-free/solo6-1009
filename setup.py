from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="tsm",
    version="0.1.0",
    description="Terminal Session Manager - Manage multiple SSH sessions efficiently",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "tsm=tsm.cli:cli",
        ],
    },
    python_requires=">=3.8",
)
