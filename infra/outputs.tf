output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "validation_queue_name" {
  value = var.queue_name
}

output "ingress_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}