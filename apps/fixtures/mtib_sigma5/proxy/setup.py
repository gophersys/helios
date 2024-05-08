from setuptools import setup, find_packages

setup(
    name="proxy",
    version="1.0",
    packages=find_packages(),
    install_requires=[
                      'grpcio',
                      'grpcio-tools',
                      'python-dotenv',
                      'flask',
                      'flask-socketio',
                      'eventlet',
                      'requests',
                      'termcolor',
                      'docker',
                      'pyyaml'
    ],
)
