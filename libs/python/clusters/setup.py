from setuptools import setup, find_packages

setup(
    name='clusters',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'kubernetes'
    ],
    python_requires='>=3.6',  # Ensure compatibility
    description='Test clusters library.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Mateo Segura',
    author_email='mateo@corekinect.com',
)