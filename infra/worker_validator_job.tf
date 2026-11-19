resource "azurerm_container_app_job" "validator" {
  name                         = var.validator_container_app_job_name
  location                     = data.azurerm_resource_group.this.location
  resource_group_name          = data.azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 0

  secret {
    name  = "azure-storage-connection-string"
    value = azurerm_storage_account.this.primary_connection_string
  }

  secret {
    name  = "jira-api-token"
    value = var.jira_api_token
  }

  secret {
    name  = "jira-cloud-id"
    value = var.jira_cloud_id
  }

  secret {
    name  = "jive-documentation"
    value = var.jive_documentation
  }

  secret {
    name  = "reg-pswd"
    value = var.container_registry_password
  }

  registry {
    server               = "${var.container_registry_username}.azurecr.io"
    username             = var.container_registry_username
    password_secret_name = "reg-pswd"
  }


  event_trigger_config {
    parallelism              = 1
    replica_completion_count = 1

    scale {
      max_executions              = 5
      min_executions              = 0
      polling_interval_in_seconds = 20

      rules {
        name             = "azure-queue-trigger"
        custom_rule_type = "azure-queue"

        metadata = {
          accountName = azurerm_storage_account.this.name
          queueName   = var.validator_queue_name
          queueLength = "1"
        }

        authentication {
          secret_name       = "azure-storage-connection-string"
          trigger_parameter = "connection"
        }
      }
    }
  }

  template {
    container {
      name   = var.validator_container_app_job_name
      image  = local.worker_image
      cpu    = 4
      memory = "8Gi"

      env {
        name  = "JIRA_API_BASE_URL"
        value = var.jira_base_url
      }

      env {
        name        = "JIRA_API_TOKEN"
        secret_name = "jira-api-token"
      }

      env {
        name  = "ALLOWED_DOMAINS"
        value = var.allowed_domains
      }

      env {
        name  = "ARGUS_SCHEMAS_VERSION"
        value = var.argus_schemas_version
      }

      env {
        name  = "JIVE_VERSION"
        value = var.jive_worker_validator_version
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
      }

      env {
        name        = "JIVE_DOCUMENTATION"
        secret_name = "jive-documentation"
      }

      env {
        name  = "MAX_EXCEL_ERRORS"
        value = "500000"
      }

      env {
        name  = "COLUMN_CHUNK_SIZE"
        value = "200"
      }

      env {
        name        = "JIRA_CLOUD_ID"
        secret_name = "jira-cloud-id"
      }

      env {
        name  = "JIRA_AUTH_TYPE"
        value = "token"
      }
    }
  }
}