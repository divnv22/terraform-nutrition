terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
  backend "azurerm" {
    resource_group_name   = "rg-terraform-state-swc-01"
    storage_account_name  = "stnutritiontfstateswc01"
    container_name        = "tfstate"
    key                   = "nutrition.tfstate"
  }
}


provider "azurerm" {
  features {}
}