from setuptools import find_packages, setup

setup(
    name="mtib-server-v2",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.74.0",
        "grpcio-tools>=1.74.0",
        "protobuf>=4.21.6",
        "python-dotenv==1.0.1",
        "pyserial==3.5",
        "termcolor==2.3.0",
        "gpiod==2.2.3",
        "xmodem==0.4.7",
        "cryptography",
        "smbus",
        "smbus2",
        "reedsolo",
        "paho-mqtt==2.1.0",
        "PyYAML==6.0.3",
        "psutil",
    ],
)
