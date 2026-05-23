from setuptools import find_packages, setup

setup(
    name="mtib-server",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.74.0",
        "grpcio-tools>=1.74.0",
        "grpcio-health-checking>=1.74.0",
        "protobuf>=4.21.6",
        "python-dotenv==1.0.1",
        "pyserial==3.5",
        "gpiod==2.2.3",
        "xmodem==0.4.7",
        "smbus2>=0.4.0",
        "paho-mqtt==2.1.0",
        "PyYAML==6.0.3",
        "termcolor>=2.0.0",
        "joulescope>=1.1.0,<1.4.0",
        "pyjoulescope_driver>=1.10.0,<1.11.0",
        "numpy>=1.24.0",
    ],
)
