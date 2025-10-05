"""Logging configuration for Agentic Redpanda."""

import logging
import logging.config
from typing import Any, Dict, Optional


def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """Set up logging configuration.
    
    Args:
        config: Optional logging configuration dictionary
    """
    default_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "agentic_redpanda.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            }
        },
        "loggers": {
            "agentic_redpanda": {
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "kafka": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    }
    
    # Merge with provided config
    if config:
        default_config.update(config)
    
    logging.config.dictConfig(default_config)
