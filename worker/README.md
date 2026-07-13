# Jive Worker
A background python worker that asynchronously pulls jobs from the queue.

## Components
```
├── Dockerfile
├── Dockerfile.local                
├── src
│   ├── tests
│   └── worker
│       ├── config.py
│       ├── excel_exporter.py       Generates multi-sheet Excel validation reports using Polars
│       ├── impact_repo_client.py   
│       ├── jira
│       │   ├── jira_client.py      Jira / JSM REST API client (with Tenacity retries & rate-limit handling)
│       │   └── models.py
│       ├── logger.py
│       ├── main.py                 Queue consumer (orchestrates validation lifecycle)
│       ├── models.py
│       ├── proforma_parser.py
│       ├── report_formatter.py     Transforms PipelineResponse into Atlassian Document Format (ADF)
│       └── worker_utils.py
```

## Local Development & Configuration

### Prerequisites
* Python 3.12+
* [uv](https://docs.astral.sh/uv/) package manager
* [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) (Local Azure Storage Emulator)

### Project Environment Setup
To create the python environment run:
```bash
uv sync  --all-extras
```

### Environment Variables
For local deployments using docker a `.env` file is required. Create a `.env` file in the api project root. `.env.example` contains the required environment variables. Change any value of `CHANGE_THIS` to the required value.

If you want to use this file locally outside of docker then the `config.py` file will need to be updated. Uncomment and configure this code in `config.py` but do not commit the change:
```python 
 model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env", # set this to the correct name and location
        env_ignore_empty=True,
        extra="ignore",
    )
```

### Running the Services Locally
To run this service use:
```bash
##########
# if the virtual environment is not active for worker
source .venv/bin/activate
##########
uv run -m worker.main
```

### Running Tests
To run tests:
```bash
uv run pytest -v
```

### Keeping code clean and formatted
To automatically format and fix some code issues use:
```bash
ruff format
ruff check --fix
```
