output "resource_group_name" {
  value = data.azurerm_resource_group.this.name
}

output "ingress_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}