from setuptools import find_packages, setup

setup(
    name="runner",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio==1.64.0",
        "grpcio-tools==1.64.0",
        "python-dotenv==1.0.1",
        "typer==0.12.3",
        "PyInquirer==1.0.3",
        "rich==13.7.1",
        "pyserial==3.5",
        "termcolor==2.4.0",
    ],
)
