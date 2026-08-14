from setuptools import find_packages, setup

setup(
    name="libs",
    version="0.2.0",
    packages=find_packages(),
    install_requires=[
        "protobuf==6.31.1",
        "grpcio==1.74.0",
        "pydantic==2.11.7",
        "pydantic-settings==2.9.1",
        "pydantic_core==2.33.2",
        "structlog==25.4.0",
        "grpcio-tools==1.74.0",
        "orjson==3.11.1",
    ],
    extras_require={
        # `libs.db` only. event_consumer and lease_manager install libs without
        # this extra: they must not reach Postgres.
        "db": [
            "SQLAlchemy==2.0.43",
            "asyncpg==0.30.0",
            "greenlet==3.2.4",
            "alembic==1.16.4",
        ],
    },
    python_requires=">=3.12.4",
)
