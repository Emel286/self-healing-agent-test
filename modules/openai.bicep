// ============================================================================
// Module: Azure OpenAI
// Deploys an Azure OpenAI account with a GPT model deployment.
// Used by the Lab 3 SRE diagnosis agent for AI-powered root cause analysis.
// ============================================================================

// ---------- Parameters ----------

@description('Azure region for the OpenAI resource')
param location string

@description('Name prefix used to generate resource names (e.g., <prefix>-openai)')
param namePrefix string

@description('Name of the GPT model to deploy (e.g., gpt-4o-mini, gpt-4o)')
param modelName string = 'gpt-4o-mini'

@description('Version of the model to deploy. If empty, uses the latest default version.')
param modelVersion string = ''

@description('Token-per-minute capacity for the model deployment (in thousands). 1 = 1K TPM.')
@minValue(1)
param deploymentCapacity int = 1

@description('Tags to apply to all resources')
param tags object = {}

// ---------- Resources ----------

// Azure OpenAI account (Cognitive Services with kind=OpenAI)
resource openaiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${namePrefix}-openai'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${namePrefix}-openai'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// GPT model deployment
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openaiAccount
  name: modelName
  sku: {
    name: 'GlobalStandard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion != '' ? modelVersion : null
    }
  }
}

// ---------- Outputs ----------

@description('The endpoint URL of the Azure OpenAI account')
output endpoint string = openaiAccount.properties.endpoint

@description('The name of the model deployment (use as AZURE_OPENAI_DEPLOYMENT)')
output deploymentName string = modelDeployment.name

@description('The resource ID of the Azure OpenAI account')
output accountId string = openaiAccount.id

@description('The name of the Azure OpenAI account (for az CLI key retrieval)')
output accountName string = openaiAccount.name
