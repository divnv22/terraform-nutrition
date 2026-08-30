resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  sku                 = "Basic"
  admin_enabled       = false

  tags = {
    environment = "dev"
    project     = "nutrition-tracker"
    managed-by  = "terraform"
  }
}