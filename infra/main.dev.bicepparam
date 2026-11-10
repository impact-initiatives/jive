using 'main.bicep'

param environmentName = 'dev'
param storageAccountName = 'jivequeuedev'
param managedEnvironmentName = 'jive-env'
param containerAppName = 'jive-ingress'
param queueJobName = 'jive-worker-validator'
param queueName = 'jive-validation-queue'
param allowedDomains = 'repository.impact-initiatives.org,impact-initiatives.atlassian.net,api.atlassian.com'
param jiraBaseUrl = 'https://api.atlassian.com/ex/jira/'
param logAnalyticsCustomerId = '0e0f0773-ad07-48a5-ade9-09d171f77e8b'
param vnetSubnetId = '/subscriptions/d23d7e9b-b2f0-4897-81ed-1cb93e8df731/resourceGroups/HQ-dev/providers/Microsoft.Network/virtualNetworks/jivevndev/subnets/default'

param imageTagApi = readEnvironmentVariable('IMAGE_TAG_API')
param imageTagWorker = readEnvironmentVariable('IMAGE_TAG_WORKER')

param registryPassword = readEnvironmentVariable('REGISTRY_PASSWORD')
param jiveApiKey = readEnvironmentVariable('JIVE_API_KEY')
param jiraApiToken = readEnvironmentVariable('JIRA_API_TOKEN')
param jiraCloudId = readEnvironmentVariable('JIRA_CLOUD_ID')
param jiveDocumentation = readEnvironmentVariable('JIVE_DOCUMENTATION')
param logAnalyticsSharedKey = readEnvironmentVariable('LOG_ANALYTICS_SHARED_KEY')
