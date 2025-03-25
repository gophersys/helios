from setuptools import find_packages, setup

setup(
    name="mtib-server",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio==1.68.1",
        "grpcio-tools==1.68.1",
        "python-dotenv==1.0.1",
        "pyserial==3.5",
        "python-dotenv==1.0.1",
        "termcolor==2.3.0",
        "gpiod==2.2.3",
        "xmodem",
        "cryptography",
        "reedsolo",
    ],
)
