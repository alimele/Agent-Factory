import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { AgentRecordDto, listAgents } from "../api";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  compiled: "Compiled",
  dev_created: "In testing",
  published: "Published",
  archived: "Archived",
};

export default function MyAgents() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { loadRecord, resetForNewAgent } = useBlueprint();

  const [agents, setAgents] = useState<AgentRecordDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents(instance)
      .then(setAgents)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load your agents"))
      .finally(() => setLoading(false));
  }, [instance]);

  function open(agent: AgentRecordDto) {
    loadRecord(agent);
    navigate(agent.status === "draft" ? "/configure" : "/launch");
  }

  return (
    <section className="page">
      <div className="sectionHeading">
        <div>
          <p className="eyebrow">MY AGENTS</p>
          <h1 className="pageTitle">Everything you've built</h1>
          <p className="pageIntro compact">Pick one up where you left it — nothing here is lost on reload.</p>
        </div>
        <button className="btn primary" onClick={() => { resetForNewAgent(); navigate("/start"); }}>+ New agent</button>
      </div>

      {loading && <div className="card" style={{ textAlign: "center", padding: 30 }}>Loading your agents…</div>}
      {error && <div className="notice errorNotice">{error}</div>}

      {!loading && !error && agents.length === 0 && (
        <div className="emptyState">
          <strong>No agents yet</strong>
          <p>Start from a template or a plain-language description.</p>
        </div>
      )}

      <div className="templateGrid">
        {agents.map((a) => (
          <button key={a.id} type="button" className="agentCard schematicCard" onClick={() => open(a)}>
            <div className="agentCardHead">
              <strong>{a.coreDraft.name}</strong>
              <span className={`statusBadge ${a.status}`}>{STATUS_LABEL[a.status] ?? a.status}</span>
            </div>
            <small>{a.coreDraft.department} · {a.coreDraft.agentType}</small>
            <p className="mutedText">{a.coreDraft.purpose}</p>
            {a.foundryAgentName && (
              <small style={{ fontFamily: "ui-monospace,SFMono-Regular,Menlo,monospace" }}>
                {a.foundryAgentName} · v{a.foundryAgentVersion}
              </small>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}
