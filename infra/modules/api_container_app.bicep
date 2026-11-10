param containerAppName string

param location string = resourceGroup().location

param environmentId string

param imageRepository string = 'jive-api'
param imageTag string

param registryServer string
param registryUsername string

@secure()
param registryPassword string

@secure()
@description('Storage connection string, supplied by main.bicep from the storage module output')
param storageConnectionString string

@secure()
param jiveApiKey string

param queueName string

var image = '${registryServer}/${imageRepository}:${imageTag}'

resource containerApp 'Microsoft.App/containerApps@2026-01-01' = {
  name: containerAppName
  location: location
  kind: 'containerapps'
  properties: {
    managedEnvironmentId: environmentId
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
          name: 'reg-pswd'
          value: registryPassword
        }
      ]
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
        allowInsecure: false
        ipSecurityRestrictions: [
          {
            name: 'Atlassian 1'
            ipAddressRange: '13.200.41.128/25'
            action: 'Allow'
          }
          {
            name: 'Atlassian 2'
            ipAddressRange: '13.236.8.224/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 3'
            ipAddressRange: '16.63.53.128/25'
            action: 'Allow'
          }
          {
            name: 'Atlassian 4'
            ipAddressRange: '18.136.214.96/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 5'
            ipAddressRange: '18.184.99.224/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 6'
            ipAddressRange: '18.234.32.224/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 7'
            ipAddressRange: '18.246.31.224/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 8'
            ipAddressRange: '43.202.69.0/25'
            action: 'Allow'
          }
          {
            name: 'Atlassian 9'
            ipAddressRange: '52.215.192.224/28'
            action: 'Allow'
          }
          {
            name: 'Atlassian 10'
            ipAddressRange: '104.192.136.0/21'
            action: 'Allow'
          }
          {
            name: 'Atlassian 11'
            ipAddressRange: '185.166.140.0/22'
            action: 'Allow'
          }
          {
            name: 'Atlassian 12'
            ipAddressRange: '131.162.88.0/21'
            action: 'Allow'
          }
        ]
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'reg-pswd'
        }
      ]
      maxInactiveRevisions: 100
    }
    template: {
      revisionSuffix: imageTag
      containers: [
        {
          image: image
          name: 'jive-api'
          command: [
            'uvicorn'
          ]
          args: [
            'api.main:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8000'
          ]
          env: [
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'azure-storage-connection-string'
            }
            {
              name: 'JIVE_QUEUE_NAME'
              value: queueName
            }
            {
              name: 'JIVE_API_KEY'
              secretRef: 'jive-api-key'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              failureThreshold: 3
              periodSeconds: 10
              successThreshold: 1
              tcpSocket: {
                port: 8000
              }
              timeoutSeconds: 5
            }
            {
              type: 'Readiness'
              failureThreshold: 48
              periodSeconds: 5
              successThreshold: 1
              tcpSocket: {
                port: 8000
              }
              timeoutSeconds: 5
            }
            {
              type: 'Startup'
              failureThreshold: 240
              initialDelaySeconds: 1
              periodSeconds: 1
              successThreshold: 1
              tcpSocket: {
                port: 8000
              }
              timeoutSeconds: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        cooldownPeriod: 300
        pollingInterval: 30
        rules: [
          {
            name: 'http-scaler'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

@description('Public FQDN of the ingress app')
output fqdn string = containerApp.properties.configuration.ingress.fqdn
