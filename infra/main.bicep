// ============================================================
// CSFLA Research Application — Azure Infrastructure
// ============================================================
// Resources:
//   - Virtual Network + subnets
//   - Azure Database for PostgreSQL Flexible Server (private)
//   - Azure Key Vault Premium (private, HSM-backed)
//   - Azure Storage Account (staging — private)
//   - Azure App Service Plan + Web App
//   - Log Analytics Workspace
//   - Managed Identity for the application
// ============================================================

@description('Environment name: dev, staging, prod')
param environment string = 'prod'

@description('Azure region')
param location string = resourceGroup().location

@description('PostgreSQL admin username — used for initial setup only')
param dbAdminUser string

@secure()
@description('PostgreSQL admin password — used for initial setup only. App uses Managed Identity.')
param dbAdminPassword string

var prefix = 'csfleak-research'
var vnetName = '${prefix}-vnet'
var appName = '${prefix}-app-${environment}'
var dbServerName = '${prefix}-db-${environment}'
var kvName = '${prefix}-kv-${environment}'
var storageName = replace('${prefix}stg${environment}', '-', '')
var logWorkspaceName = '${prefix}-logs-${environment}'
var appServicePlanName = '${prefix}-plan-${environment}'
var managedIdentityName = '${prefix}-id-${environment}'

// ── Managed Identity ─────────────────────────────────────────
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

// ── Log Analytics Workspace ───────────────────────────────────
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 730  // 2 years for audit logs
  }
}

// ── Virtual Network ───────────────────────────────────────────
resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.0.0.0/16'] }
    subnets: [
      {
        name: 'app-subnet'
        properties: {
          addressPrefix: '10.0.1.0/24'
          delegations: [
            {
              name: 'app-service-delegation'
              properties: { serviceName: 'Microsoft.Web/serverFarms' }
            }
          ]
        }
      }
      {
        name: 'db-subnet'
        properties: {
          addressPrefix: '10.0.2.0/24'
          delegations: [
            {
              name: 'postgres-delegation'
              properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' }
            }
          ]
        }
      }
      {
        name: 'private-endpoint-subnet'
        properties: {
          addressPrefix: '10.0.3.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// ── PostgreSQL Flexible Server ────────────────────────────────
resource dbServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: dbServerName
  location: location
  sku: {
    name: 'Standard_D2ds_v5'
    tier: 'GeneralPurpose'
  }
  properties: {
    administratorLogin: dbAdminUser
    administratorLoginPassword: dbAdminPassword
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: 35
      geoRedundantBackup: 'Enabled'
    }
    highAvailability: { mode: 'Disabled' }
    network: {
      delegatedSubnetResourceId: vnet.properties.subnets[1].id
      privateDnsZoneArmResourceId: postgresPrivateDns.id
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'  // Managed Identity only after initial setup
    }
  }
}

resource postgresPrivateDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

// ── Key Vault Premium (HSM-backed) ────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    sku: { family: 'A', name: 'premium' }  // Premium = HSM-backed keys
    tenantId: subscription().tenantId
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true             // Cannot be disabled once set
    enableRbacAuthorization: true           // Use Azure RBAC, not access policies
    publicNetworkAccess: 'Disabled'         // Private endpoint only
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
  }
}

// Grant pipeline Managed Identity: Key Vault Crypto User (Sign only)
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'Key Vault Crypto User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '12338af0-0e69-4776-bea7-57ae8d297424'  // Key Vault Crypto User
    )
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource kvPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${kvName}-pe'
  location: location
  properties: {
    subnet: { id: vnet.properties.subnets[2].id }
    privateLinkServiceConnections: [
      {
        name: '${kvName}-plsc'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: ['vault']
        }
      }
    ]
  }
}

// ── Storage Account (CSV staging) ────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false             // No public blobs ever
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
  }
}

resource stagingContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storageName}/default/staging'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [storageAccount]
}

// ── App Service ───────────────────────────────────────────────
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: { name: 'P1v3', tier: 'PremiumV3' }
  properties: { reserved: true }  // Linux
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${managedIdentity.id}': {} }
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      vnetRouteAllEnabled: true
      appSettings: [
        { name: 'AZURE_KEY_VAULT_URL', value: keyVault.properties.vaultUri }
        { name: 'DB_HOST', value: '${dbServerName}.postgres.database.azure.com' }
        { name: 'DB_NAME', value: 'csfleak_research' }
        { name: 'DB_USER', value: 'csfleak_app' }
        { name: 'APP_ENV', value: environment }
        // Secrets (SECRET_KEY, etc.) set manually via Azure Portal or CI pipeline — not in Bicep
      ]
    }
    virtualNetworkSubnetId: vnet.properties.subnets[0].id
  }
}

// ── Diagnostic Logs → Log Analytics ──────────────────────────
resource kvDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'kv-diagnostics'
  scope: keyVault
  properties: {
    workspaceId: logWorkspace.id
    logs: [
      { category: 'AuditEvent', enabled: true }
      { category: 'AzurePolicyEvaluationDetails', enabled: true }
    ]
  }
}

resource dbDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'db-diagnostics'
  scope: dbServer
  properties: {
    workspaceId: logWorkspace.id
    logs: [{ category: 'PostgreSQLLogs', enabled: true }]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ── Outputs ───────────────────────────────────────────────────
output appUrl string = 'https://${webApp.properties.defaultHostName}'
output keyVaultUri string = keyVault.properties.vaultUri
output dbHost string = '${dbServerName}.postgres.database.azure.com'
output managedIdentityClientId string = managedIdentity.properties.clientId
