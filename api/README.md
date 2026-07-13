# Jive API
 A lightweight FastAPI gateway immediately returns `HTTP 202 Accepted` to Jira and pushes the payload to the queue.

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
# if the virtual environment is not active for api
source .venv/bin/activate
##########
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
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


