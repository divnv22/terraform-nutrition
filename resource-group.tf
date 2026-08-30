resource "azurerm_resource_group" "lab" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    environment = "dev"
    project     = "nutrition-tracker"
    managed-by  = "terraform"
  }
}