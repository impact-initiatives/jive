# Managing Infrastructure

Infratructure is managed though [OpenTofu](https://opentofu.org/docs/intro/), a drop-in replacement for Terraform.

## Managing Changes
When creating a pull request a series of checks are performed to validate the changes. These include:
- checking code format
- checking code syntax and schema
- building a plan so that changes can be viewed and verfied. 

These checks can also be performed locally (see below). 

## Local Development
### Setup Environment
1. Install [OpenTofu] (https://opentofu.org/docs/intro/install/)
2. Create a local backend config file `infra/backend.hcl`. This should not be comitted to the repository.
```
resource_group_name  = "<your-resource-group>"
storage_account_name = "hqtfstatedev"
container_name       = "tfstate"
key                  = "jive/dev.tfstate"
subscription_id      = "<your-subscription-id>"
```
3. Login to Azure
```bash
az login
```
4. Initialise the local environment
```bash
tofu init -backend-config=backend.hcl
```
### Development Workflow
During development these commands are useful

For automatic code formatting.
```bash
tofu fmt -recursive
``` 

For validating syntax and schema.
```bash
tofu validate
``` 

For reviewing the changes and execution plan. The fake variable values can remain here as they are not being applied.
```bash
tofu plan -var-file=environments/dev.tfvars \
  -var="image_tag_api=..." -var="image_tag_worker=..." \
  -var="registry_password=..." -var="jive_api_key=..." \
  -var="jira_api_token=..." -var="jira_cloud_id=..." \
  -var="jive_documentation=..."
```

If deploying to a development environment then a plan with valid values will be required. After building a valid plan it can be applied.
```bash
tofu apply
```

You can also only plan/apply selected changes by specifying a resource
```bash
tofu plan -target=azurerm_storage_container.validated-files -var-file=environments/dev.tfvars \
  -var="image_tag_api=..." -var="image_tag_worker=..." \
  -var="registry_password=..." -var="jive_api_key=..." \
  -var="jira_api_token=..." -var="jira_cloud_id=..." \
  -var="jive_documentation=..."

tofu apply -target=azurerm_storage_container.validated-files -var-file=environments/dev.tfvars \
  -var="image_tag_api=..." -var="image_tag_worker=..." \
  -var="registry_password=..." -var="jive_api_key=..." \
  -var="jira_api_token=..." -var="jira_cloud_id=..." \
  -var="jive_documentation=..."
```