import { useEffect, useState } from "react";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { loginRequest } from "./authConfig";

// Set VITE_API_URL at build time (GitHub Actions secret/var) to the deployed
// Function App's URL, e.g. https://credo-factory-api-dev.azurewebsites.net
// Falls back to the local Azure Functions Core Tools port for `func start`.
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:7071";

type HealthResponse = {
  status: string;
  service: string;
  phase: string;
};

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { instance } = useMsal();
  const handleLogin = () => {
    instance.loginPopup(loginRequest).catch((e) => console.error(e));
  };

  const handleLogout = () => {
    instance.logoutPopup();
  };

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setHealth)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>AAF Agent Factory</h1>
      <p>Phase 0 — foundations check</p>

      {error && <p style={{ color: "crimson" }}>Error calling API: {error}</p>}

      {!error && !health && <p>Calling API…</p>}

      {health && (
        <pre
          style={{
            background: "#f4f4f4",
            padding: "1rem",
            borderRadius: "6px",
          }}
        >
          {JSON.stringify(health, null, 2)}
        </pre>
      )}
      <div>
      <AuthenticatedTemplate>
        <p>Signed in. Routing shell goes here next.</p>
        <button onClick={handleLogout}>Sign out</button>
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <button onClick={handleLogin}>Sign in</button>
      </UnauthenticatedTemplate>
    </div>
    </main>
  );
}
