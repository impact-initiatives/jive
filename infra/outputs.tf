output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "ingress_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}