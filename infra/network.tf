data "azurerm_resource_group" "this" {
  name = var.resource_group_name
}

resource "azurerm_virtual_network" "this" {
  name                = var.vnet_name
  location            = data.azurerm_resource_group.this.location
  resource_group_name = data.azurerm_resource_group.this.name
  address_space       = [var.vnet_address_prefix]
  tags                = local.tags
}

# Dedicated subnet for the Container Apps environment infrastructure
resource "azurerm_subnet" "infrastructure" {
  name                 = "cae-infrastructure"
  resource_group_name  = data.azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.infrastructure_subnet_prefix]

  delegation {
  name = "container-apps-environment"

  service_delegation {
    name    = "Microsoft.App/environments"
    actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
  }
}

  # Required so the storage account's virtualNetworkRules work
  service_endpoints = ["Microsoft.Storage"]
}