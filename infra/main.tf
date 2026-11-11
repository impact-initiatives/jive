terraform {
  required_version = ">= 1.8"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Create a dedicated state storage account (separate from the app one).
  # Supply these via -backend-config in CI or a partial backend config.
  backend "azurerm" {
    resource_group_name  = "HQ-tfstate"
    storage_account_name = "hqtfstatedev"
    container_name       = "tfstate"
    key                  = "jive/dev.tfstate"
  }
}

provider "azurerm" {
  features {}
}