resource "azurerm_container_app_environment" "this" {
  name                           = var.managed_environment_name
  location                       = data.azurerm_resource_group.this.location
  resource_group_name            = data.azurerm_resource_group.this.name
  log_analytics_workspace_id     = data.azurerm_log_analytics_workspace.this.id
  infrastructure_subnet_id       = azurerm_subnet.infrastructure.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = false

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  tags = local.tags
}