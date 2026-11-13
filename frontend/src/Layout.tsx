import { useEffect, useState } from "react";
import { Outlet, NavLink } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "./BlueprintContext";
import { getAdminStatus } from "./api";
import "./theme.css";

const pages = [
  { path: "start", label: "Start" },
  { path: "configure", label: "Configure" },
  { path: "launch", label: "Review & Launch" },
  { path: "my-agents", label: "My Agents" },
  { path: "playground", label: "Playground" },
];

// Gating rule, much simpler than the old 10-step version: Start, My Agents
// and Playground are always open (you can always start something new,
// always see what you've already built, always test something you've
// already launched). Configure and Launch need an active draft — either
// just generated on Start, or resumed from My Agents via loadRecord().
function isUnlocked(path: string, hasCoreDraft: boolean) {
  if (path === "start" || path === "my-agents" || path === "playground") return true;
  return hasCoreDraft;
}

export default function Layout() {
  const { instance } = useMsal();
  const { coreDraft } = useBlueprint();

  // Purely a UI convenience — hides the Admin links for people who don't
  // have it. The actual boundary is server-side: every /catalog-admin/*
  // route independently checks ADMIN_GROUP_IDS regardless of what this shows.
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
          <div className="sideTitle">Agent Factory</div>
          <div className="steps">
            {pages.map((p) => {
              const unlocked = isUnlocked(p.path, !!coreDraft);
              return (
                <NavLink
                  key={p.path}
                  to={unlocked ? `/${p.path}` : "#"}
                  onClick={(e) => { if (!unlocked) e.preventDefault(); }}
                  className={({ isActive }) =>
                    "step" + (isActive ? " active" : "") + (!unlocked ? " locked" : "")
                  }
                >
                  <div>
                    <strong>{p.label}</strong>
                    {!unlocked && <span>Start an agent first</span>}
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
                <NavLink
                  to="/admin/agent-templates"
                  className={({ isActive }) => "step" + (isActive ? " active" : "")}
                >
                  <div className="num">▦</div>
                  <div><strong>Agent templates</strong></div>
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
