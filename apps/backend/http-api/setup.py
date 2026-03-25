from setuptools import find_packages, setup

setup(
    name="http-api",
    version="1.0",
    packages=find_packages(),
    extras_require={
        "test": ["pytest>=8.0", "pytest-cov>=6.0"],
    },
    install_requires=[
        "grpcio>=1.75.0",
        "grpcio-tools>=1.75.0",
        "python-dotenv==1.0.1",
        "flask==3.0.2",
        "flask-socketio==5.3.6",
        "eventlet==0.36.1",
        "requests==2.26.0",
        "termcolor==2.4.0",
        "docker==7.0.0",
        "pyyaml==6.0.1",
        "dnspython==2.1.0",
        "websocket-client==1.8.0",
        "python-dateutil==2.9.0",
        "prisma==0.15.0",
        "kubernetes==34.1.0",
        "minio==7.2.18",
        "PyJWT>=2.0.0",
        "flask-cors>=5.0.0",
        "apispec>=6.0.0",
        "apispec-webframeworks>=1.0.0",
    ],
)
