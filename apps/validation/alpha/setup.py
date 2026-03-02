from setuptools import find_packages, setup

setup(
    name="concord-validation-alpha",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.75.0",
        "grpcio-tools>=1.75.0",
        "pytest>=9.0.0",
        "requests>=2.26.0",
        "sqlalchemy>=2.0.0",
        "paramiko>=3.0.0",
        "sshtunnel>=0.4.0",
        "python-dotenv>=1.0.0",
        "termcolor>=2.4.0",
        "minio>=7.2.0",
    ],
)
