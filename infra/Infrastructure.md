<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.8 |
| <a name="requirement_azurerm"></a> [azurerm](#requirement\_azurerm) | ~> 4.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | ~> 4.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [azurerm_container_app.api](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app) | resource |
| [azurerm_container_app_environment.this](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app_environment) | resource |
| [azurerm_container_app_job.validator](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app_job) | resource |
| [azurerm_storage_account.this](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account) | resource |
| [azurerm_storage_container.files](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_container) | resource |
| [azurerm_storage_queue.queues](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_queue) | resource |
| [azurerm_subnet.infrastructure](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/subnet) | resource |
| [azurerm_virtual_network.this](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/virtual_network) | resource |
| [azurerm_log_analytics_workspace.this](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/log_analytics_workspace) | data source |
| [azurerm_resource_group.this](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/resource_group) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_allowed_domains"></a> [allowed\_domains](#input\_allowed\_domains) | External domains Jive is allowed to reach. | `string` | n/a | yes |
| <a name="input_api_container_app_name"></a> [api\_container\_app\_name](#input\_api\_container\_app\_name) | Container app name for Jive Api. | `string` | `"jive-api-dev"` | no |
| <a name="input_argus_schemas_version"></a> [argus\_schemas\_version](#input\_argus\_schemas\_version) | Argus schemas version used by argus in the validator worker. | `string` | n/a | yes |
| <a name="input_container_registry_password"></a> [container\_registry\_password](#input\_container\_registry\_password) | Password for the Azure container registry. | `string` | n/a | yes |
| <a name="input_container_registry_username"></a> [container\_registry\_username](#input\_container\_registry\_username) | Username for Azure container registry. | `string` | n/a | yes |
| <a name="input_debug_ip_rules"></a> [debug\_ip\_rules](#input\_debug\_ip\_rules) | Temporary public IPs allowed to reach storage. Remove after use. | `list(string)` | `[]` | no |
| <a name="input_environment_name"></a> [environment\_name](#input\_environment\_name) | Deploymnet enviornment. dev, test, prod | `string` | `"dev"` | no |
| <a name="input_image_repository_api"></a> [image\_repository\_api](#input\_image\_repository\_api) | Image name for Api images in the Azure container registry.. | `string` | `"jive-api"` | no |
| <a name="input_image_repository_worker"></a> [image\_repository\_worker](#input\_image\_repository\_worker) | Image name for worker-validator images in the Azure container registry. | `string` | `"jive-worker-validator"` | no |
| <a name="input_image_tag_api"></a> [image\_tag\_api](#input\_image\_tag\_api) | Tag for the Api image. | `string` | n/a | yes |
| <a name="input_image_tag_worker_validator"></a> [image\_tag\_worker\_validator](#input\_image\_tag\_worker\_validator) | Tag for the worker-validator image. | `string` | n/a | yes |
| <a name="input_infrastructure_subnet_prefix"></a> [infrastructure\_subnet\_prefix](#input\_infrastructure\_subnet\_prefix) | n/a | `string` | n/a | yes |
| <a name="input_jira_api_token"></a> [jira\_api\_token](#input\_jira\_api\_token) | Jira Api token used for authentication with the Jira Api's. | `string` | n/a | yes |
| <a name="input_jira_base_url"></a> [jira\_base\_url](#input\_jira\_base\_url) | Base Url used by Jira Api's | `string` | n/a | yes |
| <a name="input_jira_cloud_id"></a> [jira\_cloud\_id](#input\_jira\_cloud\_id) | Cloud Id for the Jira account. | `string` | n/a | yes |
| <a name="input_jive_api_key"></a> [jive\_api\_key](#input\_jive\_api\_key) | Jive Api key used by Jira webhooks. | `string` | n/a | yes |
| <a name="input_jive_documentation"></a> [jive\_documentation](#input\_jive\_documentation) | Jive documentation Urls. | `string` | n/a | yes |
| <a name="input_jive_worker_validator_version"></a> [jive\_worker\_validator\_version](#input\_jive\_worker\_validator\_version) | Version of Jive worker modules running. | `string` | n/a | yes |
| <a name="input_location"></a> [location](#input\_location) | n/a | `string` | `"switzerlandnorth"` | no |
| <a name="input_log_analytics_workspace_name"></a> [log\_analytics\_workspace\_name](#input\_log\_analytics\_workspace\_name) | n/a | `string` | `"workspace-devozSg"` | no |
| <a name="input_managed_environment_name"></a> [managed\_environment\_name](#input\_managed\_environment\_name) | Name of Jive container apps environment. | `string` | `"jive-env-dev"` | no |
| <a name="input_resource_group_name"></a> [resource\_group\_name](#input\_resource\_group\_name) | Azure resource group name | `string` | n/a | yes |
| <a name="input_storage_account_name"></a> [storage\_account\_name](#input\_storage\_account\_name) | Globally unique storage account name (lowercase/numbers) | `string` | n/a | yes |
| <a name="input_validator_container_app_job_name"></a> [validator\_container\_app\_job\_name](#input\_validator\_container\_app\_job\_name) | Container job app name for Jive validation worker. | `string` | `"jive-worker-validator-dev"` | no |
| <a name="input_validator_queue_name"></a> [validator\_queue\_name](#input\_validator\_queue\_name) | Queue that triggers the validation worker. | `string` | `"jive-validation-queue"` | no |
| <a name="input_vnet_address_prefix"></a> [vnet\_address\_prefix](#input\_vnet\_address\_prefix) | n/a | `string` | n/a | yes |
| <a name="input_vnet_name"></a> [vnet\_name](#input\_vnet\_name) | Virtual network for Jive container apps environment. | `string` | `"jive-vnet-dev"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_ingress_fqdn"></a> [ingress\_fqdn](#output\_ingress\_fqdn) | n/a |
| <a name="output_storage_account_name"></a> [storage\_account\_name](#output\_storage\_account\_name) | n/a |
<!-- END_TF_DOCS -->