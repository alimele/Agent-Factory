import { IPublicClientApplication } from "@azure/msal-browser";
import { apiRequest } from "./authConfig";

// Point this at your actual Function App. Since the SPA calls it directly
// (not through an SWA-linked proxy), set this via a Vite env var so it's
// different in dev vs prod rather than hardcoded:
//   .env.development -> VITE_API_BASE_URL=http://localhost:7071/api
//   .env.production   -> VITE_API_BASE_URL=https://credo-factory-api.azurewebsites.net/api
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function getAccessToken(msalInstance: IPublicClientApplication): Promise<string> {
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
  if (!account) throw new Error("No signed-in account — user must log in first.");

  try {
    const result = await msalInstance.acquireTokenSilent({ ...apiRequest, account });
    return result.accessToken;
  } catch {
    // Silent acquisition can fail (expired session, needs interaction) —
    // fall back to a popup rather than silently failing the request.
    const result = await msalInstance.acquireTokenPopup(apiRequest);
    return result.accessToken;
  }
}

async function callApi<T>(
  msalInstance: IPublicClientApplication,
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAccessToken(msalInstance);

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ---- Types mirroring the backend's responses ----

export interface CoreBlueprintDraft {
  name: string;
  department: string;
  agentType: string;
  pattern: string;
  purpose: string;
  modelPolicy: string;
  dataClassification: string;
  humanApproval: boolean;
  externalSharing: boolean;
  requestedBy?: string;
}

export interface CatalogItem {
  id: string;
  displayName: string;
  risk?: string;
}

export interface CatalogResponse {
  department: string;
  knowledgeSources: CatalogItem[];
  tools: CatalogItem[];
  audiences: { id: string }[];
}

export interface CompileResponse {
  blueprint: Record<string, unknown>;
  foundryPayload: Record<string, unknown>;
}

// ---- The three calls ----

export function generateCoreBlueprint(msal: IPublicClientApplication, description: string) {
  return callApi<CoreBlueprintDraft>(msal, "/blueprint/core", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function getCatalogForDepartment(msal: IPublicClientApplication, department: string) {
  return callApi<CatalogResponse>(msal, `/blueprint/catalog/${encodeURIComponent(department)}`, {
    method: "GET",
  });
}

export function compileBlueprint(
  msal: IPublicClientApplication,
  args: {
    coreDraft: CoreBlueprintDraft;
    knowledgeSourceIds: string[];
    toolIds: string[];
    audienceIds: string[];
    channels?: string[];
  }
) {
  const { requestedBy, ...coreDraftFields } = args.coreDraft; // requestedBy is informational only, not part of the schema
  return callApi<CompileResponse>(msal, "/blueprint/compile", {
    method: "POST",
    body: JSON.stringify({
      coreDraft: coreDraftFields,
      knowledgeSourceIds: args.knowledgeSourceIds,
      toolIds: args.toolIds,
      audienceIds: args.audienceIds,
      channels: args.channels,
    }),
  });
}
