resource "azurerm_storage_account" "this" {
  name                     = var.storage_account_name
  location                 = data.azurerm_resource_group.this.location
  resource_group_name      = data.azurerm_resource_group.this.name
  account_tier             = "Standard"
  account_kind             = "StorageV2"
  account_replication_type = "LRS"

  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = true
  shared_access_key_enabled       = true
  default_to_oauth_authentication = false
  allow_nested_items_to_be_public = false
  dns_endpoint_type               = "Standard"

  network_rules {
    default_action             = "Deny"
    bypass                     = ["AzureServices"]
    ip_rules                   = var.debug_ip_rules
    virtual_network_subnet_ids = [azurerm_subnet.infrastructure.id]
  }

}

resource "azurerm_storage_container" "files" {
  name                  = "validated-files"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

locals {
  storage_queues = [
    "jive-validation-queue",
    "jive-validation-queue-poison",
    "jive-file-mover-queue",
    "jive-file-mover-queue-poison",
  ]
}

resource "azurerm_storage_queue" "queues" {
  for_each           = toset(local.storage_queues)
  name               = each.value
  storage_account_id = azurerm_storage_account.this.id
}
