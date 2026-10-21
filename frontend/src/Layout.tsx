import { useEffect, useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "./BlueprintContext";
import { getAdminStatus } from "./api";
import "./theme.css";

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

// Gating rule: Describe is always open. Context..Review unlock once the
// core blueprint draft exists (Describe submitted). Test & Submit unlock
// once the blueprint has been compiled on Review. Lifecycle unlocks only
// once the agent has actually been created (post-approval).
function isUnlocked(
  path: string,
  hasCoreDraft: boolean,
  hasCompiled: boolean,
  agentCreated: boolean
) {
  if (path === "describe") return true;
  if (["context", "knowledge", "tools", "behavior", "security", "review"].includes(path)) {
    return hasCoreDraft;
  }
  if (path === "test" || path === "submit") return hasCompiled;
  if (path === "lifecycle") return agentCreated;
  return false;
}

export default function Layout() {
  const { instance } = useMsal();
  const { coreDraft, compileResult, agentCreated } = useBlueprint();
  const location = useLocation();
  const currentIndex = pages.findIndex((p) => location.pathname.includes(p.path));

  // Purely a UI convenience — hides the Admin link for people who don't
  // have it. The actual boundary is server-side: every /admin/* route
  // independently checks ADMIN_GROUP_IDS regardless of what this shows.
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getAdminStatus(instance)
      .then((status) => { if (!cancelled) setIsAdmin(status.isAdmin); })
      .catch(() => { if (!cancelled) setIsAdmin(false); });
    return () => { cancelled = true; };
  }, [instance]);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <div className="logo">C</div>
          <div><b>Credo Agent Factory</b><small>Governed agent builder</small></div>
        </div>
        <button className="btn" onClick={() => instance.logoutRedirect()}>Sign out</button>
      </header>
      <div className="layout">
        <nav className="side">
          <div className="sideTitle">Create agent</div>
          <div className="steps">
            {pages.map((p, i) => {
              const unlocked = isUnlocked(p.path, !!coreDraft, !!compileResult, agentCreated);
              const done = unlocked && i < currentIndex;
              return (
                <NavLink
                  key={p.path}
                  to={unlocked ? `/${p.path}` : location.pathname}
                  onClick={(e) => { if (!unlocked) e.preventDefault(); }}
                  className={({ isActive }) =>
                    "step" + (isActive ? " active" : "") + (done ? " done" : "") + (!unlocked ? " locked" : "")
                  }
                >
                  <div className="num">{done ? "✓" : i + 1}</div>
                  <div>
                    <strong>{p.label}</strong>
                    {!unlocked && <span>Locked</span>}
                  </div>
                </NavLink>
              );
            })}
          </div>
          {isAdmin && (
            <>
              <div className="sideTitle" style={{ marginTop: 28 }}>Catalog admin</div>
              <div className="steps">
                <NavLink
                  to="/admin/knowledge-sources"
                  className={({ isActive }) => "step" + (isActive ? " active" : "")}
                >
                  <div className="num">⚙</div>
                  <div><strong>Knowledge sources</strong></div>
                </NavLink>
              </div>
            </>
          )}
        </nav>
        <main className="main">
          <div className="content">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
