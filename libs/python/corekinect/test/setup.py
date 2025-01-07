from setuptools import setup, find_packages

setup(
    name="concord",
    version="0.1",
    packages=find_packages(),
    install_requires=["pyserial>=3.5"],
    python_requires=">=3.6",
    description="Interface (iface) is an abstraction layer that offers socket-like calls on top of UART and Socket interfaces.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Mateo Segura",
    author_email="mateo@corekinect.com",
)
