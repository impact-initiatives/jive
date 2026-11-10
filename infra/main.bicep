@description('Logical environment name, used to pick defaults and tagging')
@allowed([
  'dev'
  'prod'
])
param environmentName string

param location string = 'switzerlandnorth'

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
param vnetSubnetId string = ''

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

module storage 'modules/storage_queue.bicep' = {
  name: 'storage'
  params: {
    storageAccountName: storageAccountName
    location: location
    // validationQueueName: queueName
    vnetSubnetId: vnetSubnetId
  }
}

module environment 'modules/apps_environment.bicep' = {
  name: 'managed-environment'
  params: {
    managedEnvironmentName: managedEnvironmentName
    location: location
    logAnalyticsCustomerId: logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalyticsSharedKey
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
