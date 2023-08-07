from setuptools import setup, find_packages

requirements = []
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="verinfast",
    version="0.1",
    license="Proprietary",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'verinfast = verinfast.agent:main',
        ],
    },
)
