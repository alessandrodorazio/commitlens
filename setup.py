from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="commitlens",
    version="0.1.0",
    description="Git Change Visualization Tool with AI-powered summaries",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Alessandro D'Orazio",
    author_email="me@alessandrodorazio.it",
    url="https://github.com/alessandrodorazio/commitlens",
    py_modules=["commitlens"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "openai>=1.0.0",
        "tiktoken>=0.5.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "commitlens=commitlens:main",
        ],
    },
) 