param queueJobName string

param location string = resourceGroup().location

param environmentId string

param imageRepository string = 'jive-worker-validator'
param imageTag string

param registryServer string
param registryUsername string

@secure()
param registryPassword string

@secure()
@description('Storage connection string, supplied by main.bicep from the storage module output')
param storageConnectionString string

param storageAccountName string

@secure()
param jiveApiKey string

@secure()
param jiraApiToken string

@secure()
param jiraCloudId string

@secure()
param jiveDocumentation string

param queueName string
param allowedDomains string
param jiraBaseUrl string

var image = '${registryServer}/${imageRepository}:${imageTag}'

resource job 'Microsoft.App/jobs@2026-01-01' = {
  name: queueJobName
  location: location
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      secrets: [
        {
          name: 'azure-storage-connection-string'
          value: storageConnectionString
        }
        {
          name: 'jive-api-key'
          value: jiveApiKey
        }
        {
          name: 'jira-api-token'
          value: jiraApiToken
        }
        {
          name: 'jira-cloud-id'
          value: jiraCloudId
        }
        {
          name: 'jive-documentation'
          value: jiveDocumentation
        }
        {
          name: 'reg-pswd'
          value: registryPassword
        }
      ]
      triggerType: 'Event'
      replicaTimeout: 1800
      replicaRetryLimit: 0
      eventTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
        scale: {
          minExecutions: 0
          maxExecutions: 5
          pollingInterval: 20
          rules: [
            {
              name: 'azure-queue-trigger'
              type: 'azure-queue'
              metadata: {
                accountName: storageAccountName
                queueName: queueName
              }
              auth: [
                {
                  secretRef: 'azure-storage-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          ]
        }
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'reg-pswd'
        }
      ]
    }
    template: {
      containers: [
        {
          image: image
          name: queueJobName
          env: [
            {
              name: 'JIRA_API_BASE_URL'
              value: jiraBaseUrl
            }
            {
              name: 'JIRA_API_TOKEN'
              secretRef: 'jira-api-token'
            }
            {
              name: 'ALLOWED_DOMAINS'
              value: allowedDomains
            }
            {
              name: 'JIVE_QUEUE_NAME'
              value: queueName
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'azure-storage-connection-string'
            }
            {
              name: 'JIVE_API_KEY'
              secretRef: 'jive-api-key'
            }
            {
              name: 'JIVE_DOCUMENTATION'
              secretRef: 'jive-documentation'
            }
            {
              name: 'MAX_EXCEL_ERRORS'
              value: '500000'
            }
            {
              name: 'COLUMN_CHUNK_SIZE'
              value: '200'
            }
            {
              name: 'JIRA_CLOUD_ID'
              secretRef: 'jira-cloud-id'
            }
            {
              name: 'JIRA_AUTH_TYPE'
              value: 'token'
            }
          ]
          resources: {
            cpu: 4
            memory: '8Gi'
          }
        }
      ]
    }
  }
}
