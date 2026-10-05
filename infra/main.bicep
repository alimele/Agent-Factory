// AAF Enterprise Agent Factory — Phase 0 foundations
// Deploy into Credo-Intern-RG
//
// Usage:
//   az deployment group create \
//     --resource-group Credo-Intern-RG \
//     --template-file infra/main.bicep \
//     --parameters baseName=credo

@description('Short name used as a prefix for all resources, e.g. "credo"')
param baseName string = 'credo'

@description('Azure region — defaults to the resource group region')
param location string = resourceGroup().location

// ---- Derived names ----
// Storage account names must be globally unique, lowercase, <=24 chars, no hyphens.
var storageAccountName = toLower('${baseName}facst${uniqueString(resourceGroup().id)}')
var appServicePlanName = '${baseName}-factory-plan'
var functionAppName   = '${baseName}-factory-api'
var staticWebAppName  = '${baseName}-factory-web'

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

// ---- Function App: Python v2 programming model ----
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
        // Phase 0: open so the frontend can call it from localhost and the
        // SWA hostname. Lock this down to the real frontend URL in Phase 3
        // when APIM / Entra token validation takes over auth.
        allowedOrigins: [
          '*'
        ]
      }
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
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
// Bicep creates the resource; the GitHub Action wires it to your repo
// using the deployment token from the output command below.
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
output functionAppName     string = functionApp.name
output functionAppHostname string = functionApp.properties.defaultHostName
output staticWebAppName    string = staticWebApp.name
output staticWebAppHostname string = staticWebApp.properties.defaultHostname
output storageAccountName  string = storageAccount.name

// To get the Static Web App deployment token for GitHub Actions:
//   az staticwebapp secrets list --name credo-factory-web --query "properties.apiKey" -o tsv
