import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { RouterProvider } from "react-router-dom";
import { loginRequest } from "./authConfig";
import { router } from "./router";
import { BlueprintProvider } from "./BlueprintContext";
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

  return (
    <>
      <AuthenticatedTemplate>
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