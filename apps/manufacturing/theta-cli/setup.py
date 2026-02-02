from setuptools import setup, find_packages

setup(
    name="theta-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "rich",
        "requests",
        "python-socketio[client]",
        "websocket-client",
        "python-dotenv",
    ],
    entry_points={
        "console_scripts": [
            "theta-cli=src.main:main",
        ],
    },
)
