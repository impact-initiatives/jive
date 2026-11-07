import logging

from jive_logging.logger import LoggingConfig, configure, get_logger

configure(LoggingConfig(third_party_levels={"fastexcel": logging.ERROR}))

__all__ = ["get_logger"]
