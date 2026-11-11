param managedEnvironmentName string

param location string = resourceGroup().location

@description('Log Analytics workspace customer id for container console logs')
param logAnalyticsCustomerId string

@secure()
param logAnalyticsSharedKey string

@description('Dedicated subnet for the environment (delegated to Microsoft.App/environments).')
param infrastructureSubnetId string

resource environment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: managedEnvironmentName
  location: location
  properties: {
    vnetConfiguration: {
      internal: false
      infrastructureSubnetId: infrastructureSubnetId
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    zoneRedundant: false
    kedaConfiguration: {}
    daprConfiguration: {}
    customDomainConfiguration: {}
    workloadProfiles: [
      {
        workloadProfileType: 'Consumption'
        name: 'Consumption'
      }
    ]
    peerAuthentication: {
      mtls: {
        enabled: false
      }
    }
    peerTrafficConfiguration: {
      encryption: {
        enabled: false
      }
    }
    publicNetworkAccess: 'Enabled'
  }
}

output environmentId string = environment.id
