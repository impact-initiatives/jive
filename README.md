# JIVE — Jira IMPACT Validation Engine

**JIVE** (Jira IMPACT Validation Engine) is a mono-repository for managing automated workflows that interact with Jira and other impact infrastrcture. It includes a number of shared and re-useable componets that Jive workers can use to perform specific workflows. Each has its own environment configuration and deployment files. 

See the `readme` in the individual components below for more details.

## Project Structure

```text

├── api                     
├── workers                 
├── common                  
└── local        Local exploration and local Docker Compose setup

```


### api
[api](api) - a FastAPI ingress (webhook endpoint). Used for receiving requests from Jira.

### workers
Individual workers that are deployed as container apps or jobs.

[validator](workers/validator/) - An asynchronous, event-driven microservice that automates Research Quality Assurance (RQA) data validation workflows.

### common
Shared components that can be resued by workers or other components.

[argus](common/argus/) - Framework for validating datasets submitted to RQA.

[jira](common/jira/) - Reusable components for interacting with Jira tickets.

[jive_logging](common/jive_logging/) - Logging componenets to facilitate standardised logging for all Jive components.


