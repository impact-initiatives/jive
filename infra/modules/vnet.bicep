param vnetName string

param location string = resourceGroup().location

@description('Address space for the VNet, e.g. 10.20.0.0/22')
param vnetAddressPrefix string

@description('Infrastructure subnet for the Container Apps environment. /26 recommended, /27 minimum. Must not overlap vnetAddressPrefix space used elsewhere.')
param infrastructureSubnetPrefix string

resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
  }
}

@description('Dedicated subnet for Container Apps environment infrastructure and app outbound traffic')
resource infrastructureSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: vnet
  name: 'cae-infrastructure'
  properties: {
    addressPrefix: infrastructureSubnetPrefix
    delegations: [
      {
        name: 'container-apps-environment'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
    serviceEndpoints: [
      {
        service: 'Microsoft.Storage'
        locations: [
          'switzerlandnorth'
        ]
      }
    ]
  }
}

output infrastructureSubnetId string = infrastructureSubnet.id
output vnetId string = vnet.id
