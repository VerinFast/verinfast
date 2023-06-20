from setuptools import setup, find_packages

setup(
    name="verinfast",
    version="0.1",
    license="Proprietary",
    packages=find_packages(),
    install_requires=[
        'multimetric',
        'PyYAML',
        'requests',
        'semgrep'
    ],
    entry_points={
        'console_scripts': [
            'verinfast = verinfast.agent:main',
        ],
    },
)
