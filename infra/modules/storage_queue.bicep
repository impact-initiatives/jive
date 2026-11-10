@description('Globally unique storage account name (lowercase/numbers, 3-24 chars)')
param storageAccountName string

param location string = resourceGroup().location

// @description('Name of the main validation queue; the poison queue gets "-poison" appended')
// param validationQueueName string = 'jive-validation-queue'

@description('Subnet allowed to reach the storage account. Leave empty for no vnet rule.')
param vnetSubnetId string = ''

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
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: empty(vnetSubnetId)
        ? []
        : [
            {
              id: vnetSubnetId
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

// resource validationQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2026-06-01' = {
//   parent: queueService
//   name: validationQueueName
// }

// resource poisonQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2026-06-01' = {
//   parent: queueService
//   name: '${validationQueueName}-poison'
// }

@secure()
@description('Connection string for the deployed storage account')
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

output storageAccountName string = storageAccount.name
// output validationQueueName string = validationQueue.name
