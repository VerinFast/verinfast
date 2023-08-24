from setuptools import setup, find_packages

setup(
    author='Igor Hatarist',
    author_email='igor@hatari.st',
    name='pygments_tsx',
    packages=find_packages(),
    py_modules=['pygments_tsx'],
    version='0.1',
    entry_points="""
    [pygments.lexers]
    tsx=pygments_tsx:TypeScriptXLexer
    """,
)
