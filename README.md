# CREDO Enterprise Agent Factory

CREDO Agent Factory is an enterprise agent-authoring application. It combines a React and TypeScript web app with a Python Azure Functions API to guide a signed-in user through defining an agent, choosing approved department-scoped knowledge and tools, reviewing governance checks, and creating and testing an unpublished development agent in Microsoft Foundry.

## What the application does

The current authoring flow is:

1. **Describe** — turn a plain-language request into a draft blueprint using the configured Foundry model.
2. **Configure** — review the generated context and choose department-approved knowledge sources and tools. Set behavior preferences and select an approved audience.
3. **Review** — compile the blueprint and Foundry payload, run the pre-deployment policy evaluation, and create a development agent if the policy result does not fail.
4. **Test** — send a prompt to the created development agent and view its response.

The web app has ten navigation steps: Describe, Context, Knowledge, Tools, Behavior, Security, Review, Test, Submit, and Lifecycle. **Submit and Lifecycle are currently placeholders.** There is no publish or approval workflow yet. The implemented Foundry creation endpoint creates an unpublished development version; a flagged policy result can proceed to development testing, while a failed result blocks creation.

Policy checks cover identity and department access, approved model and catalog selections, tool risk and agent type, data classification, human-approval requirements, external sharing, network status, ownership, lifecycle, and (at the pre-publish stage) evaluation results. The current UI runs the pre-deployment stage; the policy API supports pre-publish evaluation, but no post-test pre-publish flow is wired into the UI.

## Repository layout

```text
backend/functions/       Python Azure Functions API, blueprint and policy logic
frontend/                React, TypeScript, Vite, and Microsoft Entra sign-in
scripts/                 Foundry IQ connection and agent smoke-test examples
.github/workflows/       Azure Functions and Azure Static Web Apps workflows
.vscode/                 Local editor and Functions tasks/settings
```

## Requirements

- Python 3.11 (the Functions deployment workflow uses Python 3.11)
- Node.js and npm
- [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) v4
- An Azure sign-in usable by `DefaultAzureCredential` for the configured Foundry, API Center, and App Configuration resources
- Access to the configured Microsoft Entra application and API

The backend reads required Azure resource settings when the application starts. Set up the backend settings below before starting the Functions host.

## Local development

### Backend

In PowerShell:

```powershell
cd backend\functions
if (-not (Test-Path local.settings.json)) {
    Copy-Item local.settings.json.example local.settings.json
}
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Add the application settings in the next section to `Values` in `local.settings.json`, then sign in to Azure using a credential supported by `DefaultAzureCredential` (for example, `az login`) and start the host:

```powershell
func start
```

The Functions host normally listens at `http://localhost:7071`.

### Backend application settings

The following settings are read by the application:

| Setting | Purpose |
| --- | --- |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription containing the API Center service |
| `RESOURCE_GROUP` | Resource group containing that API Center service |
| `APICENTER_SERVICE_NAME` | API Center service name |
| `APPCONFIG_ENDPOINT` | Endpoint of the Azure App Configuration store containing knowledge-source entries |
| `GROUP_DEPARTMENT_MAP` | JSON object mapping Entra group IDs to department names, for example `{"<group-object-id>":"HR"}` |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry project endpoint used for blueprint generation |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name used for blueprint generation |
| `FOUNDRY_ACTUAL_PROJECT_ENDPOINT` | Foundry project endpoint used to create and query development agents |

Optional settings include `APICENTER_WORKSPACE_NAME` (defaults to `default`), `KNOWLEDGE_KEY_PREFIX` (defaults to `knowledge-sources/`), `APICENTER_CATALOG_CACHE_TTL`, `APICENTER_SPEC_CACHE_TTL`, `KNOWLEDGE_CACHE_TTL_SECONDS`, `LOCAL_DEV_MODE`, and per-policy model deployment overrides (`FOUNDRY_MODEL_APPROVED_GENERAL_ENTERPRISE`, `FOUNDRY_MODEL_APPROVED_HIGH_ACCURACY`, and `FOUNDRY_MODEL_APPROVED_FAST_LOWCOST`).

Catalogs are populated from Azure resources: knowledge sources come from App Configuration and tools come from API Center. The configured resources must contain entries marked ready for the relevant department. `GROUP_DEPARTMENT_MAP` must map the signed-in user's Entra group claims to the department names used by the catalogs.

The API expects Azure Static Web Apps or App Service Easy Auth to provide the authenticated `x-ms-client-principal` header. `LOCAL_DEV_MODE=true` enables a local requester identity for endpoints that use it, but does not supply the group claims needed by department and policy authorization. It is not a replacement for configuring authenticated department access.

### Frontend

Create `frontend/.env.local` with the URL of the Functions API and the API scope used by the policy evaluation call:

```dotenv
VITE_API_URL=http://localhost:7071
VITE_API_SCOPE=api://<application-client-id>/access_as_user
```

Use the Function App's base URL for `VITE_API_URL` in a deployed environment; do not append `/api` or a trailing slash. The Microsoft Entra tenant, client ID, and sign-in/API scopes are also configured in `frontend/src/authConfig.ts`; ensure they match the app registration and exposed API used by your environment. For local browser sign-in, register the Vite origin as a redirect URI and allow it in the Function App's CORS settings.

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Vite normally serves the app at `http://localhost:5173`. To check the production bundle locally, run `npm run build` and then `npm run preview`.

## HTTP API

The routes below are exposed under the Azure Functions `/api` prefix:

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/blueprint/core` | Generate the core blueprint draft from a description |
| `GET` | `/api/blueprint/catalog/{department}` | Return the signed-in user's approved department catalog |
| `POST` | `/api/blueprint/compile` | Validate selections and return the governance blueprint and Foundry payload |
| `POST` | `/api/policy/evaluate` | Evaluate a blueprint at `pre_deploy` or `pre_publish` stage |
| `POST` | `/api/blueprint/create-test-agent` | Revalidate policy and create an unpublished Foundry development agent |
| `POST` | `/api/blueprint/test-agent` | Run a prompt against a development agent owned by the signed-in user |

These routes expect authenticated identity context. The backend revalidates blueprint fields and catalog IDs instead of trusting the browser's selections.

## Testing and validation

Build the frontend with:

```powershell
cd frontend
npm ci
npm run build
```

`backend/functions/api/blueprint/test_phase2.py` is a manually run blueprint/payload smoke-test script, and the scripts under `scripts/` demonstrate Foundry IQ setup and agent invocation. These are resource-backed examples rather than a self-contained offline test suite: they require the relevant Azure settings, seeded catalog entries, Azure credentials, and access to the configured services.

## Deployment workflows

The GitHub Actions workflows deploy from the `main` branch:

- The Azure Functions workflow packages `backend/functions` and deploys it to the configured Function App on pushes to `main` (or when manually dispatched), using Azure login with GitHub Actions OpenID Connect.
- The Azure Static Web Apps workflow builds and deploys `frontend` on pushes to `main`. It also creates and closes Static Web Apps preview environments for pull requests targeting `main`.

The workflows require their configured GitHub Actions secrets. The Static Web Apps build uses `AZURE_STATIC_WEB_APPS_API_TOKEN_WHITE_ROCK_0594C0300`, `VITE_API_URL`, and `VITE_API_SCOPE`. The Functions workflow uses its configured Azure client ID, tenant ID, and subscription ID secrets for OpenID Connect.

## Important safety and implementation notes

- Testing sends a real prompt to Foundry. An attached action tool may call its connected API; use read-only or sandboxed tools until an approval workflow is implemented.
- The blueprint's human-approval setting is a policy and instruction input; it is **not** an interactive technical approval gate for tool calls. MCP action tools currently default to no per-call approval.
- Creating a development agent does not publish it or configure production audience enforcement. The audience selection is recorded in the blueprint metadata; deployment-time access controls and the Submit/Lifecycle workflows remain to be completed.
