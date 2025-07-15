from src.core.logging import setup_logging

# Logging setup before any module imports
setup_logging()

from fastapi import FastAPI
from src.core.setup import create_app

app: FastAPI = create_app()
