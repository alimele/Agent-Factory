import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { RouterProvider } from "react-router-dom";
import { loginRequest } from "./authConfig";
import { router } from "./router";
import { BlueprintProvider } from "./BlueprintContext"

export default function App() {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch((e) => console.error(e));
  };

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