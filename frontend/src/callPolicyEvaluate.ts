// Call this instead of putting "requester" in the JSON body — the
// access token now carries identity + department (via the roles claim).

import { IPublicClientApplication } from "@azure/msal-browser";

const VITE_API_URL = import.meta.env.VITE_API_URL;
const API_SCOPE = import.meta.env.VITE_API_SCOPE;

export async function callPolicyEvaluate(
  msalInstance: IPublicClientApplication,
  body: { blueprint: object; stage: "pre_deploy" | "pre_publish"; testResults?: object; blueprintId?: string }
) {
  const account = msalInstance.getActiveAccount();
  if (!account) throw new Error("No signed-in account — user must log in first");

  const { accessToken } = await msalInstance.acquireTokenSilent({
    scopes: [API_SCOPE],
    account,
  });

  const res = await fetch(`${VITE_API_URL}/api/policy/evaluate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`Policy evaluate failed: ${res.status} ${await res.text()}`);
  return res.json();
}
