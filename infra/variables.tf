variable "environment_name" {
  description = "Deploymnet enviornment. dev, test, prod"
  type        = string
  default     = "dev"
}

variable "location" {
  type    = string
  default = "switzerlandnorth"
}



# --- Network ---
variable "vnet_name" {
  description = "Virtual network for Jive container apps environment."
  type        = string
  default     = "jive-vnet-dev"
}

variable "vnet_address_prefix" {
  type = string
}

variable "infrastructure_subnet_prefix" {
  type = string
}

# --- Names ---
variable "storage_account_name" {
  description = "Globally unique storage account name (lowercase/numbers)"
  type        = string
}

variable "managed_environment_name" {
  description = "Name of Jive container apps environment."
  type        = string
  default     = "jive-env-dev"
}

variable "api_container_app_name" {
  description = "Container app name for Jive Api."
  type        = string
  default     = "jive-api-dev"
}

variable "validator_container_app_job_name" {
  description = "Container job app name for Jive validation worker."
  type        = string
  default     = "jive-worker-validator-dev"
}

variable "validator_queue_name" {
  description = "Queue that triggers the validation worker."
  type        = string
  default     = "jive-validation-queue"
}

# --- Images / registry ---
variable "image_repository_api" {
  description = "Image name for Api images in the Azure container registry.."
  type        = string
  default     = "jive-api"
}

variable "image_repository_worker" {
  description = "Image name for worker-validator images in the Azure container registry."
  type        = string
  default     = "jive-worker-validator"
}

variable "image_tag_api" {
  description = "Tag for the Api image."
  type        = string
}

variable "image_tag_worker_validator" {
  description = "Tag for the worker-validator image."
  type        = string
}

variable "jive_worker_validator_version" {
  description = "Version of Jive worker modules running."
  type        = string
}

# --- App config ---
variable "allowed_domains" {
  description = "External domains Jive is allowed to reach."
  type        = string
  default     = "repository.impact-initiatives.org,impact-initiatives.atlassian.net,api.atlassian.com"
}

variable "jira_base_url" {
  description = "Base Url used by Jira Api's"
  type        = string
}

variable "log_analytics_workspace_name" {
  type    = string
  default = "workspace-devozSg"
}

variable "debug_ip_rules" {
  description = "Temporary public IPs allowed to reach storage. Remove after use."
  type        = list(string)
  default     = []
}

# --- Secrets (passed via TF_VAR_* environment variables) ---
variable "resource_group_name" {
  description = "Azure resource group name"
  type        = string
  sensitive   = true
}

variable "container_registry_username" {
  description = "Username for Azure container registry."
  type        = string
  sensitive   = true
}

variable "container_registry_password" {
  description = "Password for the Azure container registry."
  type        = string
  sensitive   = true
}

variable "jive_api_key" {
  description = "Jive Api key used by Jira webhooks."
  type        = string
  sensitive   = true
}

variable "jira_api_token" {
  description = "Jira Api token used for authentication with the Jira Api's."
  type        = string
  sensitive   = true
}

variable "jira_cloud_id" {
  description = "Cloud Id for the Jira account."
  type        = string
  sensitive   = true
}

variable "jive_documentation" {
  description = "Jive documentation Urls."
  type        = string
  sensitive   = true
}