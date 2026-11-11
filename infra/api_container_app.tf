resource "azurerm_container_app" "api" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = data.azurerm_resource_group.this.name
  revision_mode                = "Single"

  secret {
    name  = "azure-storage-connection-string"
    value = azurerm_storage_account.this.primary_connection_string
  }

  secret {
    name  = "jive-api-key"
    value = var.jive_api_key
  }

  secret {
    name  = "reg-pswd"
    value = var.registry_password
  }

  registry {
    server               = var.registry_server
    username             = var.registry_username
    password_secret_name = "reg-pswd"
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }

    ip_security_restriction {
      name             = "Atlassian 1"
      action           = "Allow"
      ip_address_range = "13.200.41.128/25"
    }

    ip_security_restriction {
      name             = "Atlassian 2"
      action           = "Allow"
      ip_address_range = "13.236.8.224/28"
    }

    ip_security_restriction {
      name             = "Atlassian 3"
      action           = "Allow"
      ip_address_range = "16.63.53.128/25"
    }

    ip_security_restriction {
      name             = "Atlassian 4"
      action           = "Allow"
      ip_address_range = "18.136.214.96/28"
    }

    ip_security_restriction {
      name             = "Atlassian 5"
      action           = "Allow"
      ip_address_range = "18.184.99.224/28"
    }

    ip_security_restriction {
      name             = "Atlassian 6"
      action           = "Allow"
      ip_address_range = "18.234.32.224/28"
    }

    ip_security_restriction {
      name             = "Atlassian 7"
      action           = "Allow"
      ip_address_range = "18.246.31.224/28"
    }

    ip_security_restriction {
      name             = "Atlassian 8"
      action           = "Allow"
      ip_address_range = "43.202.69.0/25"
    }

    ip_security_restriction {
      name             = "Atlassian 9"
      action           = "Allow"
      ip_address_range = "52.215.192.224/28"
    }

    ip_security_restriction {
      name             = "Atlassian 10"
      action           = "Allow"
      ip_address_range = "104.192.136.0/21"
    }

    ip_security_restriction {
      name             = "Atlassian 11"
      action           = "Allow"
      ip_address_range = "185.166.140.0/22"
    }

    ip_security_restriction {
      name             = "Atlassian 12"
      action           = "Allow"
      ip_address_range = "131.162.88.0/21"
    }
  }

    template {
    min_replicas = 1
    max_replicas = 10
    # cooldown_period / polling_interval omitted — see note below

    http_scale_rule {
      name                = "http-scaler"
      concurrent_requests = "10"
    }

    container {
      name    = "jive-api"
      image   = local.api_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["uvicorn"]
      args    = ["api.main:app", "--host", "0.0.0.0", "--port", "8000"]

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
      }

      env {
        name  = "JIVE_QUEUE_NAME"
        value = var.queue_name
      }

      env {
        name        = "JIVE_API_KEY"
        secret_name = "jive-api-key"
      }

      startup_probe {
        transport         = "TCP"
        port              = 8000
        initial_delay     = 1
        interval_seconds  = 1
        timeout           = 3
        failure_count_threshold = 240
      }

      liveness_probe {
        transport         = "TCP"
        port              = 8000
        interval_seconds  = 10
        timeout           = 5
        failure_count_threshold = 3
      }

      readiness_probe {
        transport         = "TCP"
        port              = 8000
        interval_seconds  = 5
        timeout           = 5
        failure_count_threshold = 48
      }
    }
  }
}