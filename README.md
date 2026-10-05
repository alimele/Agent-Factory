# AAF Enterprise Agent Factory — Phase 0 skeleton

Hello-world foundation: a Function App + a Static Web App, deployed via
Bicep and GitHub Actions. Proves the CI/CD loop before Phase 1 adds real
pages and logic.

## What's here

```
infra/                  Bicep template (storage, plan, Function App, Static Web App)
backend/functions/       Python v2 Function App — GET /api/health
frontend/                Vite + React + TS — calls /api/health and renders it
.github/workflows/       CI/CD: deploy-backend.yml, deploy-frontend.yml
```

## 1. Deploy the infrastructure

You've already created `rg-aaf-dev` (and test/prod). Deploy the Bicep template into it:

```bash
az deployment group create \
  --resource-group rg-aaf-dev \
  --template-file infra/main.bicep \
  --parameters baseName=aaf environment=dev
```

Note the outputs — `functionAppName` and `staticWebAppHostname` — you'll need them next.

## 2. Get the deployment credentials for GitHub Actions

**Function App publish profile:**

```bash
az functionapp deployment list-publishing-profiles \
  --name aaf-factory-api-dev \
  --resource-group rg-aaf-dev \
  --xml
```

Copy the full XML output into a GitHub repo secret named `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`.

**Static Web App deployment token:**

```bash
az staticwebapp secrets list \
  --name aaf-factory-web-dev \
  --query "properties.apiKey" -o tsv
```

Copy that into a GitHub repo secret named `AZURE_STATIC_WEB_APPS_API_TOKEN`.

**Frontend → backend URL:**

Add one more repo secret, `VITE_API_URL`, set to the Function App's URL, e.g.
`https://aaf-factory-api-dev.azurewebsites.net` (from the `functionAppHostname`
output, prefixed with `https://`).

## 3. Push to `main`

Both workflows trigger automatically on push (each only runs when its own
folder changes). Check the Actions tab — both should go green. Then open the
Static Web App's hostname in a browser: you should see the Phase 0 page
showing the JSON response from `/api/health`.

## Local development

**Backend** (requires [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)):

```bash
cd backend/functions
cp local.settings.json.example local.settings.json
pip install -r requirements.txt
func start
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

With both running locally, the frontend's default `API_URL` fallback
(`http://localhost:7071`) will hit your local Function host directly — no
env var needed for local dev.

## What's deliberately not here yet

- Auth on the Function App (anonymous for now — real auth lands in Phase 3 via APIM/Entra)
- Key Vault (not needed until real credentials show up)
- test/prod resource group deployments (redeploy the same Bicep with `environment=test` / `environment=prod` when you get there)
