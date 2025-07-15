import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from typing import Any, Dict


class SimpleJSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "fastapi-app"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry)


def get_logging_config() -> Dict[str, Any]:
    env = os.getenv("ENVIRONMENT", "development")
    use_json = env == "production"
    service_name = os.getenv("SERVICE_NAME", "fastapi-app")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": SimpleJSONFormatter,
                "service_name": service_name,
            },
            "standard": {
                "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if use_json else "standard",
                "stream": "ext://sys.stdout",
                "level": log_level,
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "fastapi": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "app": {"handlers": ["console"], "level": log_level, "propagate": False},
        },
    }

    return config


def setup_logging() -> None:
    try:
        config = get_logging_config()
        logging.config.dictConfig(config)
        logging.getLogger(__name__).info("Logging configured successfully")
    except Exception as e:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )
        logging.getLogger(__name__).exception(
            "Failed to configure logging. Using basic config."
        )
