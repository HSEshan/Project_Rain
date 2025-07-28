from libs.logging.logger import setup_logging

# Logging setup before any module imports
setup_logging(service_name="ws_gateway")

from fastapi import FastAPI
from src.core.setup import create_app

app: FastAPI = create_app()
