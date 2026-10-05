// AAF Enterprise Agent Factory — Phase 0 foundations
// Deploy at resource-group scope into rg-aaf-dev (or -test / -prod).
//
// Usage:
//   az deployment group create \
//     --resource-group rg-aaf-dev \
//     --template-file main.bicep \
//     --parameters baseName=aaf environment=dev

@description('Short name used as a prefix for all resources, e.g. "aaf"')
param baseName string = 'aaf'

@description('Environment suffix: dev, test, or prod')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

// ---- Derived names ----
// Storage account names must be globally unique, lowercase, <=24 chars, no hyphens.
var storageAccountName = toLower('${baseName}fac${environment}${uniqueString(resourceGroup().id)}')
var appServicePlanName = '${baseName}-plan-${environment}'
var functionAppName = '${baseName}-factory-api-${environment}'
var staticWebAppName = '${baseName}-factory-web-${environment}'

// ---- Storage account (required by the Function App runtime) ----
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

// ---- Consumption plan (Linux, pay-per-execution, has a free monthly grant) ----
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // required for Linux
  }
}

// ---- Function App: Python, v2 programming model ----
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      minTlsVersion: '1.2'
      cors: {
        // Phase 0: wide open so the hello-world frontend can call it from
        // any localhost port / the SWA default hostname. Lock this down to
        // the real frontend origin once that's fixed, and move auth to
        // APIM/Entra in Phase 3 rather than relying on CORS for security.
        allowedOrigins: [
          '*'
        ]
      }
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsFeatureFlags'
          value: 'EnableWorkerIndexing' // required for the Python v2 decorator model
        }
      ]
    }
  }
}

// ---- Static Web App: hosts the React frontend ----
// Note: Bicep creates the resource itself, but linking it to your GitHub repo
// for CI/CD is done by the GitHub Action using the deployment token below —
// Bicep does not need your GitHub PAT.
resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

// ---- Outputs ----
output functionAppName string = functionApp.name
output functionAppHostname string = functionApp.properties.defaultHostName
output staticWebAppName string = staticWebApp.name
output staticWebAppHostname string = staticWebApp.properties.defaultHostname
output storageAccountName string = storageAccount.name

// To get the Static Web App deployment token for GitHub Actions (secret, not an output):
//   az staticwebapp secrets list --name <staticWebAppName> --query "properties.apiKey" -o tsv
