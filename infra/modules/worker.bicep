// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Worker Container App (Queue Consumer)
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string

@description('Container App Environment resource ID')
param environmentId string

@description('Full image name including ACR and tag')
param imageName string

@description('Key Vault URI for secret references')
param keyVaultUri string

@description('Name of the worker Container App')
param appName string = 'jive-worker'

@description('Name of the validation queue')
param queueName string = 'jive-validation-queue'

resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      // No ingress — worker is internal only
      secrets: [
        {
          name: 'storage-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/storage-connection-string'
          identity: 'system'
        }
        {
          name: 'jira-api-email'
          keyVaultUrl: '${keyVaultUri}secrets/jira-api-email'
          identity: 'system'
        }
        {
          name: 'jira-api-token'
          keyVaultUrl: '${keyVaultUri}secrets/jira-api-token'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: imageName
          command: ['python', 'worker.py']
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'storage-connection-string'
            }
            {
              name: 'JIRA_API_EMAIL'
              secretRef: 'jira-api-email'
            }
            {
              name: 'JIRA_API_TOKEN'
              secretRef: 'jira-api-token'
            }
            {
              name: 'JIVE_QUEUE_NAME'
              value: queueName
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'queue-scaling'
            custom: {
              type: 'azure-queue'
              metadata: {
                queueName: queueName
                queueLength: '1'
                connectionFromEnv: 'AZURE_STORAGE_CONNECTION_STRING'
              }
            }
          }
        ]
      }
    }
  }
}

@description('Managed Identity Principal ID')
output principalId string = workerApp.identity.principalId
