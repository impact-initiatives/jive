# Jira Integration
Reusable components for interacting with Jira.

### Prerequisites
* Python 3.14+
* [uv](https://docs.astral.sh/uv/) package manager

## Componenets

```
├── src
   ├── jira
   │   ├── config.py            Required enviornment variables and config options
   │   ├── jira_client.py       Main client for interacting with Jira
   │   ├── models.py            Api models for parsing responses
   │   └── proforma_parser.py   Parses a Jira form
   └── tests
```

## Add Jira to a workflow
To use these componenets in another project within this repository it needs to be included in the projects `pyproject.toml` file.

First add it as a dependency
```toml
dependencies = [
    ...
    "jira",

]
```

Then add the source directory
```toml
[tool.uv.sources]
jira = { path = "../../common/jira", editable = true  }
```

