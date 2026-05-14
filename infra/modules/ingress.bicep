// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Ingress Container App (FastAPI)
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string

@description('Container App Environment resource ID')
param environmentId string

@description('Full image name including ACR and tag')
param imageName string

@description('Key Vault URI for secret references')
param keyVaultUri string

@description('Name of the ingress Container App')
param appName string = 'jive-ingress'

resource ingressApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      secrets: [
        {
          name: 'storage-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/storage-connection-string'
          identity: 'system'
        }
        {
          name: 'jive-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/jive-api-key'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ingress'
          image: imageName
          command: ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000']
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'storage-connection-string'
            }
            {
              name: 'JIVE_API_KEY'
              secretRef: 'jive-api-key'
            }
            {
              name: 'JIVE_QUEUE_NAME'
              value: 'jive-validation-queue'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              periodSeconds: 30
              failureThreshold: 3
              initialDelaySeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

@description('Ingress FQDN')
output fqdn string = ingressApp.properties.configuration.ingress.fqdn

@description('Managed Identity Principal ID')
output principalId string = ingressApp.identity.principalId
