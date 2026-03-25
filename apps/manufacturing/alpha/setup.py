from setuptools import find_packages, setup

setup(
    name="manufacturing-alpha",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.75.0",
        "grpcio-tools>=1.75.0",
        "python-dotenv==1.0.1",
        "requests==2.26.0",
        "docker==7.0.0",
        "termcolor==2.4.0",
    ],
)
