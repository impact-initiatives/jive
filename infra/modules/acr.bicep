// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Azure Container Registry
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string

@description('Name of the Container Registry')
param acrName string

@description('SKU for the Container Registry')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: true
  }
}

@description('ACR login server URL')
output loginServer string = acr.properties.loginServerHost

@description('ACR resource ID')
output acrId string = acr.id
