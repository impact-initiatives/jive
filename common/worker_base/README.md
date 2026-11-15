# Worker Base 
Base worker class to use when a worker is getting Jira issues from the queue. Includes shared code for interacting with the queue, downloading datasets and reporting updates to Jira.

### Prerequisites
* Python 3.14+
* [uv](https://docs.astral.sh/uv/) package manager

## Componenets

```
├── src
   ├── worker_base
   │   ├── config.py                Required enviornment variables and config options
   │   ├── base.py                  Main client for interacting with Jira, Queue
   │   ├── models.py                Models for parsing responses from Jira sent to the Api
   │   ├── impact_repo_clinet.py    Webscraping framework for downloading datasets from the impact repository
   │   └── dataset_utils.py         Orchestrator for downloading a dataset
   └── tests
```

## Add Worker Base to a workflow
To use these componenets in another project within this repository it needs to be included in the projects `pyproject.toml` file.

First add it as a dependency
```toml
dependencies = [
    ...
    "worker_base",

]
```

Then add the source directory
```toml
[tool.uv.sources]
jira = { path = "../../common/worker_base", editable = true  }
```

