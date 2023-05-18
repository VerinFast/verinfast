from setuptools import setup, find_packages

setup(
    name="sosagent",
    version="0.1",
    license="Proprietary",
    packages=find_packages(),
    install_requires=[
        'multimetric',
        'PyYAML',
        'requests'
    ],
    entry_points={
        'console_scripts': [
            'sosagent = sosagent.agent:main',
        ],
    },
)
