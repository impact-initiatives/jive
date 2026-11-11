@description('Logical environment name, used to pick defaults and tagging')
@allowed([
  'dev'
  'prod'
])
param environmentName string

param location string = 'switzerlandnorth'

param vnetName string = 'jive-cae-vnet'
@description('VNet address space, e.g. 10.20.0.0/22')
param vnetAddressPrefix string
@description('CAE infrastructure subnet prefix, e.g. 10.20.0.0/26')
param infrastructureSubnetPrefix string
param debugIpRules array = []

param storageAccountName string
param managedEnvironmentName string = 'jive-env'
param containerAppName string = 'jive-api'
param queueJobName string = 'jive-worker-validator'

param imageTagApi string
param imageTagWorker string
param registryServer string = 'acrimpact.azurecr.io'
param registryUsername string = 'acrimpact'

param queueName string = 'jive-validation-queue'
param allowedDomains string
param jiraBaseUrl string

param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

@secure()
param registryPassword string

@secure()
param jiveApiKey string

@secure()
param jiraApiToken string

@secure()
param jiraCloudId string

@secure()
param jiveDocumentation string

module vnet 'modules/vnet.bicep' = {
  name: 'vnet'
  params: {
    vnetName: vnetName
    location: location
    vnetAddressPrefix: vnetAddressPrefix
    infrastructureSubnetPrefix: infrastructureSubnetPrefix
  }
}

module environment 'modules/apps_environment.bicep' = {
  name: 'managed-environment'
  params: {
    managedEnvironmentName: managedEnvironmentName
    location: location
    logAnalyticsCustomerId: logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalyticsSharedKey
    infrastructureSubnetId: vnet.outputs.infrastructureSubnetId
  }
}

module storage 'modules/storage_queue.bicep' = {
  name: 'storage'
  params: {
    storageAccountName: storageAccountName
    location: location
    allowedSubnetIds: [vnet.outputs.infrastructureSubnetId]
    debugIpRules: debugIpRules
  }
}

module containerApp 'modules/api_container_app.bicep' = {
  name: 'container-app'
  params: {
    containerAppName: containerAppName
    location: location
    environmentId: environment.outputs.environmentId
    imageTag: imageTagApi
    registryServer: registryServer
    registryUsername: registryUsername
    registryPassword: registryPassword
    storageConnectionString: storage.outputs.connectionString
    jiveApiKey: jiveApiKey
    queueName: queueName
  }
}

module queueJob 'modules/validator_worker.bicep' = {
  name: 'queue-job'
  params: {
    queueJobName: queueJobName
    location: location
    environmentId: environment.outputs.environmentId
    imageTag: imageTagWorker
    registryServer: registryServer
    registryUsername: registryUsername
    registryPassword: registryPassword
    storageConnectionString: storage.outputs.connectionString
    storageAccountName: storage.outputs.storageAccountName
    jiveApiKey: jiveApiKey
    jiraApiToken: jiraApiToken
    jiraCloudId: jiraCloudId
    jiveDocumentation: jiveDocumentation
    queueName: queueName
    allowedDomains: allowedDomains
    jiraBaseUrl: jiraBaseUrl
  }
}

output storageAccountName string = storage.outputs.storageAccountName
output validationQueueName string = queueName
output ingressFqdn string = containerApp.outputs.fqdn
