@description('Globally unique storage account name (lowercase/numbers, 3-24 chars)')
param storageAccountName string

param location string = resourceGroup().location

@description('Subnet IDs allowed to reach this storage account (typically the Container Apps environment subnet).')
param allowedSubnetIds array = []

@description('Temporary public IP/CIDRs for debugging/portal access. Remove after use — an empty array means storage is only reachable from the listed subnets.')
param debugIpRules array = []

resource storageAccount 'Microsoft.Storage/storageAccounts@2026-06-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    defaultToOAuthAuthentication: false
    publicNetworkAccess: 'Enabled'
    dnsEndpointType: 'Standard'
    encryption: {
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: false
      services: {
        blob: {
          keyType: 'Account'
          enabled: true
        }
        file: {
          keyType: 'Account'
          enabled: true
        }
      }
    }
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: [
        for ip in debugIpRules: {
          ipAddressOrRange: ip
          action: 'Allow'
        }
      ]
      virtualNetworkRules: [
        for subnetId in allowedSubnetIds: {
          id: subnetId
          action: 'Allow'
        }
      ]
    }
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2026-06-01' = {
  parent: storageAccount
  name: 'default'
}

// (queues intentionally omitted here — see note below)

@secure()
@description('Connection string for the deployed storage account')
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

output storageAccountName string = storageAccount.name
