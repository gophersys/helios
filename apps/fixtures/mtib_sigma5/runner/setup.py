from setuptools import setup, find_packages

setup(
    name="mtib_server",
    version="1.0",
    packages=find_packages(),
    install_requires=[
                      'grpcio',
                      'grpcio-tools',
                      'python-dotenv',
                      'typer[all]',
                      'PyInquirer',
                      'rich',
                      'pyserial',
                      'termcolor'
    ],
)
