output "subscription_id" {
  value       = var.subscription_id
  description = "Deployment subscription ID."
}

output "resource_group_name" {
  value       = azurerm_resource_group.rg.name
  description = "Created resource group name."
}

output "resource_group_location" {
  value       = azurerm_resource_group.rg.location
  description = "Deployment region."
}

output "acr_login_server" {
  value       = azurerm_container_registry.acr.login_server
  description = "ACR login server. Push images with: az acr build --registry <name> --image aios:latest ."
}

output "container_app_name" {
  value       = azurerm_container_app.app.name
  description = "Azure Container App name."
}

output "container_app_url" {
  value       = "https://${azurerm_container_app.app.latest_revision_fqdn}"
  description = "Production URL of the AIOS Container App."
}

output "user_assigned_identity_id" {
  value       = azurerm_user_assigned_identity.app.id
  description = "User-assigned managed identity resource ID."
}

output "user_assigned_identity_client_id" {
  value       = azurerm_user_assigned_identity.app.client_id
  description = "User-assigned managed identity client ID."
}

output "key_vault_name" {
  value       = azurerm_key_vault.kv.name
  description = "Key Vault name for post-provision secrets."
}

output "key_vault_uri" {
  value       = azurerm_key_vault.kv.vault_uri
  description = "Key Vault URI."
}

output "search_service_name" {
  value       = azurerm_search_service.search.name
  description = "Azure AI Search service name backing Foundry IQ knowledge bases."
}

output "search_service_endpoint" {
  value       = "https://${azurerm_search_service.search.name}.search.windows.net"
  description = "Azure AI Search endpoint."
}

output "foundry_knowledge_base_name" {
  value       = "aios-kb"
  description = "Knowledge base name used by AIOS."
}

output "foundry_knowledge_source_name" {
  value       = "aios-kb"
  description = "Knowledge source name used by AIOS."
}

output "postgres_server_name" {
  value       = azurerm_postgresql_flexible_server.psql.name
  description = "PostgreSQL server name."
}

output "postgres_server_fqdn" {
  value       = azurerm_postgresql_flexible_server.psql.fqdn
  description = "PostgreSQL fully qualified domain name."
}

output "postgres_database_name" {
  value       = azurerm_postgresql_flexible_server_database.db.name
  description = "Application database name."
}

output "postgres_admin_username" {
  value       = var.postgres_admin_username
  description = "Database administrator username."
}

output "openai_account_name" {
  value       = azurerm_cognitive_account.openai.name
  description = "Azure OpenAI account name."
}

output "openai_endpoint" {
  value       = azurerm_cognitive_account.openai.endpoint
  description = "Azure OpenAI endpoint."
}

output "openai_primary_deployment_name" {
  value       = azurerm_cognitive_deployment.primary.name
  description = "Primary reasoning deployment name."
}

output "openai_fallback_deployment_name" {
  value       = azurerm_cognitive_deployment.fallback.name
  description = "Fallback deployment name."
}

output "openai_embedding_deployment_name" {
  value       = azurerm_cognitive_deployment.embedding.name
  description = "Embedding deployment name."
}
