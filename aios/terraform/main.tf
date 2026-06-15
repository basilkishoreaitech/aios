terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.35"
    }
    azurecaf = {
      source  = "aztfmod/azurecaf"
      version = "~> 1.2"
    }
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

data "azurerm_client_config" "current" {}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID for deployment."
}

variable "developer_user_object_id" {
  type        = string
  default     = ""
  description = "Optional Microsoft Entra object ID for the sandbox developer user who should receive interactive RBAC assignments. If omitted, Terraform uses the currently signed-in Azure principal."
}

variable "developer_user_email" {
  type        = string
  default     = ""
  description = "Optional informational email/UPN for the sandbox developer user. Terraform does not resolve RBAC from email directly; use developer_user_object_id for the actual assignment target."
}

variable "project_name" {
  type        = string
  default     = "aios"
  description = "Short project name used for resource naming."
}

variable "key_vault_name_override" {
  type        = string
  default     = ""
  description = "Optional explicit Key Vault name override. Use this when the original vault name is blocked by soft-delete or purge protection."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment environment name."
}

variable "location" {
  type        = string
  default     = "francecentral"
  description = "Primary Azure region for the workload resources."
}

variable "postgres_admin_username" {
  type        = string
  description = "Administrator username for PostgreSQL Flexible Server."
}

variable "postgres_admin_password" {
  type        = string
  sensitive   = true
  description = "Administrator password for PostgreSQL Flexible Server."
}

variable "jwt_secret_key" {
  type        = string
  sensitive   = true
  description = "JWT signing key for AIOS."
}

variable "allowed_origin" {
  type        = string
  default     = "http://localhost:8000"
  description = "Origin allowed to call the API from the current environment."
}

variable "app_service_sku" {
  type        = string
  default     = "B1"
  description = "App Service plan SKU."
}

variable "postgres_sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "PostgreSQL Flexible Server SKU."
}

variable "search_sku" {
  type        = string
  default     = "basic"
  description = "Azure AI Search SKU supporting knowledge bases."
}

variable "openai_deployment_sku_name" {
  type        = string
  default     = "GlobalStandard"
  description = "SKU used for Azure OpenAI model deployments."
}

variable "openai_primary_deployment_name" {
  type        = string
  default     = "gpt-5.4"
}

variable "openai_primary_model_name" {
  type        = string
  default     = "gpt-5.4"
}

variable "openai_primary_model_version" {
  type        = string
  default     = "2026-03-05"
}

variable "openai_fallback_deployment_name" {
  type        = string
  default     = "gpt-5.4-mini"
}

variable "openai_fallback_model_name" {
  type        = string
  default     = "gpt-5.4-mini"
}

variable "openai_fallback_model_version" {
  type        = string
  default     = "2026-03-17"
}

variable "openai_critic_deployment_name" {
  type        = string
  default     = "gpt-4.1"
  description = "Adversarial critic model (A8) — intentionally a different model family from the primary."
}

variable "openai_critic_model_name" {
  type        = string
  default     = "gpt-4.1"
}

variable "openai_critic_model_version" {
  type        = string
  default     = "2025-04-14"
}

variable "openai_embedding_deployment_name" {
  type        = string
  default     = "text-embedding-3-small"
}

variable "openai_embedding_model_name" {
  type        = string
  default     = "text-embedding-3-small"
}

variable "openai_embedding_model_version" {
  type        = string
  default     = "1"
}

locals {
  base_name = "${var.project_name}-${var.environment}"
  app_runtime_environment = contains(["dev", "development", "test", "local"], lower(var.environment)) ? "development" : "production"
  developer_principal_id = trimspace(var.developer_user_object_id) != "" ? trimspace(var.developer_user_object_id) : data.azurerm_client_config.current.object_id
  key_vault_name = trimspace(var.key_vault_name_override) != "" ? trimspace(var.key_vault_name_override) : azurecaf_name.key_vault.result
  database_url = format(
    "postgresql+asyncpg://%s:%s@%s/%s?ssl=require",
    var.postgres_admin_username,
    urlencode(var.postgres_admin_password),
    azurerm_postgresql_flexible_server.psql.fqdn,
    azurerm_postgresql_flexible_server_database.db.name,
  )
  tags = {
    app         = var.project_name
    environment = var.environment
    managedBy   = "terraform"
    workload    = "agents-league"
  }
}

resource "azurecaf_name" "resource_group" {
  name          = local.base_name
  resource_type = "azurerm_resource_group"
  clean_input   = true
}

resource "azurecaf_name" "log_analytics" {
  name          = local.base_name
  resource_type = "azurerm_log_analytics_workspace"
  clean_input   = true
}

resource "azurecaf_name" "application_insights" {
  name          = local.base_name
  resource_type = "azurerm_application_insights"
  clean_input   = true
}

resource "azurecaf_name" "key_vault" {
  name          = local.base_name
  resource_type = "azurerm_key_vault"
  clean_input   = true
}

resource "azurecaf_name" "postgres_server" {
  name          = local.base_name
  resource_type = "azurerm_postgresql_flexible_server"
  clean_input   = true
}

resource "azurecaf_name" "search_service" {
  name          = local.base_name
  resource_type = "azurerm_search_service"
  clean_input   = true
}

resource "azurecaf_name" "openai_account" {
  name          = local.base_name
  resource_type = "azurerm_cognitive_account"
  clean_input   = true
}

resource "azurecaf_name" "user_assigned_identity" {
  name          = local.base_name
  resource_type = "azurerm_user_assigned_identity"
  clean_input   = true
}

resource "azurerm_resource_group" "rg" {
  name     = azurecaf_name.resource_group.result
  location = var.location
  tags     = local.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = azurecaf_name.user_assigned_identity.result
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = azurecaf_name.log_analytics.result
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_application_insights" "appi" {
  name                = azurecaf_name.application_insights.result
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"
  tags                = local.tags
}

resource "azurerm_key_vault" "kv" {
  name                          = local.key_vault_name
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  public_network_access_enabled = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 7
  tags                          = local.tags
}

resource "azurerm_role_assignment" "kv_current_user" {
  scope                = azurerm_key_vault.kv.id
  role_definition_id   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b86a8fe4-44ce-4948-aee5-eccb2c155cd7"
  principal_id         = local.developer_principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "kv_app_identity" {
  scope                = azurerm_key_vault.kv.id
  role_definition_id   = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b86a8fe4-44ce-4948-aee5-eccb2c155cd7"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "openai_current_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = local.developer_principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "openai_app_identity" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "search_current_user_service_contributor" {
  scope                = azurerm_search_service.search.id
  role_definition_name = "Search Service Contributor"
  principal_id         = local.developer_principal_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "search_current_user_index_data_contributor" {
  scope                = azurerm_search_service.search.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = local.developer_principal_id
  principal_type       = "User"
}

resource "azurerm_postgresql_flexible_server" "psql" {
  name                   = azurecaf_name.postgres_server.result
  resource_group_name    = azurerm_resource_group.rg.name
  location               = azurerm_resource_group.rg.location
  version                = "16"
  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password
  sku_name               = var.postgres_sku_name
  storage_mb             = 32768
  zone                   = "1"
  tags                   = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "db" {
  name      = "${var.project_name}${var.environment}"
  server_id = azurerm_postgresql_flexible_server.psql.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.psql.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_search_service" "search" {
  name                = azurecaf_name.search_service.result
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = var.search_sku
  semantic_search_sku = "standard"
  local_authentication_enabled = true
  tags                = local.tags
}

resource "azurerm_cognitive_account" "openai" {
  name                          = azurecaf_name.openai_account.result
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  public_network_access_enabled = true
  custom_subdomain_name         = azurecaf_name.openai_account.result
  tags                          = local.tags
}

resource "azurerm_cognitive_deployment" "primary" {
  name                 = var.openai_primary_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_primary_model_name
    version = var.openai_primary_model_version
  }

  sku {
    name     = var.openai_deployment_sku_name
    capacity = 1
  }
}

resource "azurerm_cognitive_deployment" "fallback" {
  name                 = var.openai_fallback_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_fallback_model_name
    version = var.openai_fallback_model_version
  }

  sku {
    name     = var.openai_deployment_sku_name
    capacity = 1
  }
}

resource "azurerm_cognitive_deployment" "critic" {
  name                 = var.openai_critic_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_critic_model_name
    version = var.openai_critic_model_version
  }

  sku {
    name     = var.openai_deployment_sku_name
    capacity = 1
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.openai_embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_embedding_model_name
    version = var.openai_embedding_model_version
  }

  sku {
    name     = var.openai_deployment_sku_name
    capacity = 1
  }
}

# ── Container Registry (image built via: az acr build, no local Docker needed) ──
resource "azurerm_container_registry" "acr" {
  name                = "acr${replace(local.base_name, "-", "")}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

# ── Container Apps (scale-to-zero = pauses when idle, saves cost) ──
resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.base_name}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
  tags                       = local.tags
}

resource "azurerm_container_app" "app" {
  name                         = "ca-${local.base_name}"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  # Sensitive values stored as Container App secrets
  secret {
    name  = "database-url"
    value = local.database_url
  }
  secret {
    name  = "openai-api-key"
    value = azurerm_cognitive_account.openai.primary_access_key
  }
  secret {
    name  = "foundry-iq-key"
    value = azurerm_search_service.search.primary_key
  }
  secret {
    name  = "appinsights-conn-str"
    value = azurerm_application_insights.appi.connection_string
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    # min_replicas = 0 → scales to zero when idle (pauses, no compute cost)
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "aios"
      # Placeholder until first `az acr build` — updated by the deploy step
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "ENVIRONMENT"
        value = local.app_runtime_environment
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "ALLOWED_ORIGIN"
        value = var.allowed_origin
      }
      env {
        name  = "KB_PROVIDER"
        value = "foundry_iq"
      }
      env {
        name  = "REQUIRE_LIVE_MODELS"
        value = "true"
      }
      env {
        name  = "REQUIRE_LIVE_WEB_SEARCH"
        value = "false"
      }
      env {
        name  = "ENABLE_SEED_SAMPLE_DATA"
        value = "false"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = "2024-12-01-preview"
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_PRIMARY"
        value = azurerm_cognitive_deployment.primary.name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_FALLBACK"
        value = azurerm_cognitive_deployment.fallback.name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_UTILITY"
        value = azurerm_cognitive_deployment.fallback.name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_CRITIC"
        value = azurerm_cognitive_deployment.critic.name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_EMBEDDING"
        value = azurerm_cognitive_deployment.embedding.name
      }
      env {
        name  = "FOUNDRY_IQ_ENDPOINT"
        value = "https://${azurerm_search_service.search.name}.search.windows.net"
      }
      env {
        name  = "FOUNDRY_IQ_API_VERSION"
        value = "2024-07-01"
      }
      env {
        name  = "FOUNDRY_IQ_INDEX_NAME"
        value = "aios-kb"
      }
      # Sensitive values pulled from secrets
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "FOUNDRY_IQ_KEY"
        secret_name = "foundry-iq-key"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-conn-str"
      }
    }
  }
}

resource "azurerm_monitor_diagnostic_setting" "container_app" {
  name                       = "diag-${var.project_name}-${var.environment}"
  target_resource_id         = azurerm_container_app_environment.env.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }
}
