from setuptools import setup, find_packages

setup(
    name="concord-build-worker",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.28",
    ],
)
