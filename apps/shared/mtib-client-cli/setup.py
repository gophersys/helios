from setuptools import find_packages, setup

setup(
    name="mtib-client-cli",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio==1.62.0",
        "grpcio-tools==1.62.0",
        "grpcio-health-checking==1.62.0",
        "python-dotenv==1.0.1",
        "pyserial==3.5",
        "termcolor==2.3.0",
        "typer==0.10.0",
    ],
)
