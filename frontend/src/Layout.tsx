import { Outlet, NavLink } from "react-router-dom";
import { useMsal } from "@azure/msal-react";

const pages = [
  { path: "describe", label: "Describe" },
  { path: "context", label: "Context" },
  { path: "knowledge", label: "Knowledge" },
  { path: "tools", label: "Tools" },
  { path: "behavior", label: "Behavior" },
  { path: "security", label: "Security" },
  { path: "review", label: "Review" },
  { path: "test", label: "Test" },
  { path: "submit", label: "Submit" },
  { path: "lifecycle", label: "Lifecycle" },
];

export default function Layout() {
  const { instance } = useMsal();

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav style={{ width: 200, padding: "1rem", borderRight: "1px solid #ddd" }}>
        <h3>AAF Factory</h3>
        {pages.map((p) => (
          <div key={p.path} style={{ margin: "0.5rem 0" }}>
            <NavLink to={p.path}>{p.label}</NavLink>
          </div>
        ))}
        <button onClick={() => instance.logoutRedirect()} style={{ marginTop: "1rem" }}>
          Sign out
        </button>
      </nav>
      <main style={{ flex: 1, padding: "2rem" }}>
        <Outlet />
      </main>
    </div>
  );
}