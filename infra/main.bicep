// ──────────────────────────────────────────────────────────────
// JIVE Infrastructure — Main Orchestrator
// ──────────────────────────────────────────────────────────────
// Deploys all JIVE resources into a single resource group.
// Usage:
//   az deployment group create \
//     --resource-group rg-impact-etl \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/prod.bicepparam
// ──────────────────────────────────────────────────────────────

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name of the Storage Account')
param storageAccountName string

@description('Name of the Container Registry')
param acrName string

@description('Name of the Key Vault')
param keyVaultName string

@description('Name of the Container App Environment')
param environmentName string

@description('Docker image name (without tag)')
param imageName string

@description('Docker image tag')
param imageTag string = 'latest'

// ─── Storage Account + Queue ─────────────────────────────────
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    location: location
    storageAccountName: storageAccountName
  }
}

// ─── Container Registry ──────────────────────────────────────
module acr 'modules/acr.bicep' = {
  name: 'acr-deployment'
  params: {
    location: location
    acrName: acrName
  }
}

// ─── Container App Environment ───────────────────────────────
module env 'modules/environment.bicep' = {
  name: 'environment-deployment'
  params: {
    location: location
    environmentName: environmentName
  }
}

// ─── Ingress Container App ───────────────────────────────────
module ingress 'modules/ingress.bicep' = {
  name: 'ingress-deployment'
  params: {
    location: location
    environmentId: env.outputs.environmentId
    imageName: '${acr.outputs.loginServer}/${imageName}:${imageTag}'
    keyVaultUri: kv.outputs.vaultUri
  }
}

// ─── Worker Container App ────────────────────────────────────
module worker 'modules/worker.bicep' = {
  name: 'worker-deployment'
  params: {
    location: location
    environmentId: env.outputs.environmentId
    imageName: '${acr.outputs.loginServer}/${imageName}:${imageTag}'
    keyVaultUri: kv.outputs.vaultUri
  }
}

// ─── Key Vault ───────────────────────────────────────────────
// Both ingress and worker managed identities need Key Vault access.
module kv 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    ingressPrincipalId: ingress.outputs.principalId
    workerPrincipalId: worker.outputs.principalId
    storageConnectionString: storage.outputs.connectionString
  }
}

// ─── Outputs ─────────────────────────────────────────────────
output ingressFqdn string = ingress.outputs.fqdn
output acrLoginServer string = acr.outputs.loginServer
output keyVaultUri string = kv.outputs.vaultUri
