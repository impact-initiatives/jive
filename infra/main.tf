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

  }
}

provider "azurerm" {
  features {}
}