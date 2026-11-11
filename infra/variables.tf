variable "environment_name" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "switzerlandnorth"
}

variable "resource_group_name" {
  type    = string
  default = "HQ-dev"
}

# --- Network ---
variable "vnet_name" {
  type    = string
  default = "jive-vnet-dev"
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
  type    = string
  default = "jive-env-dev"
}

variable "container_app_name" {
  type    = string
  default = "jive-api-dev"
}

variable "queue_job_name" {
  type    = string
  default = "jive-worker-validator-dev"
}

variable "queue_name" {
  type    = string
  default = "jive-validation-queue"
}

# --- Images / registry ---
variable "image_repository_api" {
  type    = string
  default = "jive-api"
}

variable "image_repository_worker" {
  type    = string
  default = "jive-worker-validator"
}

variable "image_tag_api" {
  type = string
}

variable "image_tag_worker" {
  type = string
}

variable "registry_server" {
  type    = string
  default = "acrimpact.azurecr.io"
}

variable "registry_username" {
  type    = string
  default = "acrimpact"
}

# --- App config ---
variable "allowed_domains" {
  type = string
}

variable "jira_base_url" {
  type = string
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
variable "registry_password" {
  type      = string
  sensitive = true
}

variable "jive_api_key" {
  type      = string
  sensitive = true
}

variable "jira_api_token" {
  type      = string
  sensitive = true
}

variable "jira_cloud_id" {
  type      = string
  sensitive = true
}

variable "jive_documentation" {
  type      = string
  sensitive = true
}