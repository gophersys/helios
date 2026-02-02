from setuptools import setup, find_packages

setup(
    name="mtib_client_v2",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.62.0",
        "grpcio-tools>=1.62.0",
        "protobuf>=4.21.6",
    ],
    python_requires=">=3.10",
    description="MTIB V2 gRPC Client",
    author="CoreKinect",
)
