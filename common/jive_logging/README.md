# Jive Logging
Logging componenets to facilitate standardised logging throughout Jive components.

### Prerequisites
* Python 3.14+
* [uv](https://docs.astral.sh/uv/) package manager

## Add Jive Logging to a workflow
To use these componenets in another project within this repository it needs to be included in the projects `pyproject.toml` file.

First add it as a dependency
```toml
dependencies = [
    ...
    "jive_logging",
]
```

Then add the source directory
```toml
[tool.uv.sources]
jive_logging = { path = "../../common/jive_logging", editable = true  }
```

## Configuring the logger for a project
A parent project (ie, one of the workers) is able to configure the logger. This allows the configuration of paramaters like the file name, the logging level and other file properties. It also allows configuring the logging level of dependencies.

To do this, create a python file, ie `logs.py` in the projects `src` folder.

In that file include the required paramaters.

```python
import logging

from jive_logging.logger import LoggingConfig, configure, get_logger

configure(
    LoggingConfig(
        log_file="jive-validator.log", third_party_levels={"fastexcel": logging.ERROR}
    )
)

__all__ = ["get_logger"]
```

Then in the projects modules, import the logger from this file
```python
from .logs import get_logger

logger = get_logger("jive.validator")
```

**NOTE**
This should not be done for dependencies (ie, projects stored in common) as the parent projects configuration may not take effect if the dependencies configuration is loaded first.