import logging
import sys
from typing import Any


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("predicta.api")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            '{"logger":"%(name)s","level":"%(levelname)s","message":"%(message)s","request_id":"%(request_id)s"}'
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def bind_request_id(logger: logging.Logger, request_id: str) -> logging.LoggerAdapter[Any]:
    return logging.LoggerAdapter(logger, extra={"request_id": request_id})
