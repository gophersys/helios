from setuptools import find_packages, setup

setup(
    name="validation_sigma5_tests",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.75.0",
        "grpcio-tools>=1.75.0",
        "python-dotenv==1.0.1",
        "requests>=2.27.1",
        "docker==7.0.0",
        "termcolor==2.4.0",
        "hvac==2.3.0",
        "minio==7.2.18",
        "python-logging-loki==0.3.1",
    ],
)
