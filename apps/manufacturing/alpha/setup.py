from setuptools import find_packages, setup

setup(
    name="manufacturing-alpha",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.75.0",
        "grpcio-tools>=1.75.0",
        "python-dotenv>=1.0.0",
        "requests>=2.26.0",
        "pytest>=9.0.0",
        "pytest-timeout>=2.0.0",
    ],
    extras_require={
        "test": [
            "pytest>=9.0.0",
            "pytest-timeout>=2.0.0",
        ],
    },
)
