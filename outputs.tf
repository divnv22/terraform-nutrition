output "resource_group_name" {
  description = "Name of the Terraform-managed Resource Group"
  value       = azurerm_resource_group.lab.name
}

output "resource_group_id" {
  description = "Azure Resource ID of the Resource Group"
  value       = azurerm_resource_group.lab.id
}