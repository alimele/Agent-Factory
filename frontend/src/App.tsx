import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { RouterProvider } from "react-router-dom";
import { loginRequest } from "./authConfig";
import { router } from "./router";
import { BlueprintProvider } from "./BlueprintContext"
import { callPolicyEvaluate } from "./callPolicyEvaluate";
import { useEffect } from "react";

export default function App() {
  const { instance, accounts } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch((e) => console.error(e));
  };

  useEffect(() => {
  if (!instance.getActiveAccount() && accounts.length > 0) {
    instance.setActiveAccount(accounts[0]);
  }
}, [instance, accounts]);

  async function handleTestPolicyEvaluate() {
  const sampleBlueprint = {
    department: "Finance",
    modelPolicy: "approved-general-enterprise",
    knowledgeSources: [], tools: [],
    dataClassification: "Internal",
    humanApproval: false, externalSharing: false,
    owner: "ali@test.com", reviewPeriodDays: 180,
  };

  try {
    const res = await callPolicyEvaluate(instance, { blueprint: sampleBlueprint, stage: "pre_deploy" });
    console.log("Policy evaluation result:", res);
  } catch (err) {
    console.error("Policy evaluate failed:", err);
  }
}

  return (
    <>
      <AuthenticatedTemplate>
        <button onClick={handleTestPolicyEvaluate}>Test Policy Evaluate</button>
        <BlueprintProvider>
        <RouterProvider router={router} />
        </BlueprintProvider>
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <div style={{ padding: "2rem" }}>
          <h1>CREDO Agent Factory</h1>
          <button onClick={handleLogin}>Sign in</button>
        </div>
      </UnauthenticatedTemplate>
    </>
  );
}