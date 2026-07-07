// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Azure Key Vault
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string

@description('Name of the Key Vault')
param keyVaultName string

@description('Object ID of the ingress Container App managed identity')
param ingressPrincipalId string

@description('Object ID of the worker Container App managed identity')
param workerPrincipalId string

@description('Tenant ID for the Key Vault')
param tenantId string = subscription().tenantId

@description('Storage Account connection string to store as a secret')
@secure()
param storageConnectionString string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Grant the ingress identity "Key Vault Secrets User" role
resource ingressSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, ingressPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: ingressPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Grant the worker identity "Key Vault Secrets User" role
resource workerSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workerPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Seed secrets — these will be populated manually or via a separate secure process.
// Bicep creates the secret entries; actual values are set via Azure CLI or Portal.
resource secretStorageConn 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'storage-connection-string'
  properties: {
    value: storageConnectionString
  }
}

// Placeholder secrets — values must be set manually after first deployment
resource secretJiraEmail 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jira-api-email'
  properties: {
    value: 'PLACEHOLDER-SET-VIA-PORTAL'
  }
}

resource secretJiraToken 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jira-api-token'
  properties: {
    value: 'PLACEHOLDER-SET-VIA-PORTAL'
  }
}

resource secretApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jive-api-key'
  properties: {
    value: 'PLACEHOLDER-SET-VIA-PORTAL'
  }
}

@description('Key Vault URI')
output vaultUri string = keyVault.properties.vaultUri

@description('Key Vault resource ID')
output keyVaultId string = keyVault.id
