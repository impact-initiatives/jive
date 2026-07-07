// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Container App Environment
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string

@description('Name of the Container App Environment')
param environmentName string

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

@description('Container App Environment resource ID')
output environmentId string = environment.id
