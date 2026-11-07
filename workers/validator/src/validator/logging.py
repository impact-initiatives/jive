
from jive_logging.logger import LoggingConfig, configure, get_logger

configure(
    LoggingConfig(
        log_file="jive-validator.log",
    )
)

__all__ = ["get_logger"]
