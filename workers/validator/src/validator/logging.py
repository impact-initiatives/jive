import logging

from jive_logging.logger import LoggingConfig, configure, get_logger

configure(
    LoggingConfig(log_file="jive-validator.log", third_party_levels={"fastexcel": logging.ERROR})
)

__all__ = ["get_logger"]
