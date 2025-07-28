from setuptools import find_packages, setup

setup(
    name="libs",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "protobuf==6.31.1",
        "grpcio==1.74.0",
        "pydantic==2.11.5",
        "pydantic-settings==2.9.1",
        "pydantic_core==2.33.2",
        "structlog==25.4.0",
        "grpcio-tools==1.74.0",
    ],
    python_requires=">=3.12.4",
)
