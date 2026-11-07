import logging

from jive_logging.logger import get_logger

for noisy in ["fastexcel"]:
    logging.getLogger(noisy).setLevel(logging.ERROR)

__all__ = ["get_logger"]
