from setuptools import setup, find_packages

setup(
    name="mtib_runner_client",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio==1.62.0",
        "grpcio-tools==1.62.0",
        "protobuf>=4.21.6",
        "python-dotenv==1.0.1",
        "pyserial==3.5",
        "termcolor==2.3.0",
        "gpiod==2.2.3",
        "xmodem",
        "cryptography",
        "smbus",
        "reedsolo",
        "tkinter",
    ],
)
