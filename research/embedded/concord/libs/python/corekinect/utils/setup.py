import os

from setuptools import find_packages, setup

# Read the contents of README.md for the long description
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="corekinect-utils",
    author="Jared Walton, Mateo Segura",
    author_email="jared@corekinect.com;mateo@corekinect.com",
    description="General Utility Libraries",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "termcolor==2.4.0",
        "python-dotenv==1.0.1",
        "packaging>=21.0",
    ],
    tests_require=[
        "pytest>=8.0",
        "pytest-cov>=4.0",
    ],
)
