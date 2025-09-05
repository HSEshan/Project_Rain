import os

from libs.logging import setup_logging

# Logging setup before any module imports
log_format = os.getenv("LOG_FORMAT", "json")
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(service_name="rest_api", log_format=log_format, level=log_level)

from fastapi import FastAPI
from src.core.setup import create_app

app: FastAPI = create_app()
