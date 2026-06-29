import logging

import pytest


@pytest.fixture(autouse=True)
def _celery_logging_compat():
    """Celery trace logs pass dict args that break pytest log formatting."""
    celery_loggers = (
        logging.getLogger("celery"),
        logging.getLogger("celery.app.trace"),
        logging.getLogger("celery.utils.functional"),
    )
    previous = [(logger, logger.propagate, logger.level) for logger in celery_loggers]
    for logger in celery_loggers:
        logger.propagate = False
        logger.setLevel(logging.WARNING)
    yield
    for logger, propagate, level in previous:
        logger.propagate = propagate
        logger.setLevel(level)
