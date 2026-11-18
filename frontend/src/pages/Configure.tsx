import { useEffect, useState } from "react";
import ToolConnectionModal from "../ToolConnectionModal";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { getCatalogForDepartment, getToolOperations, saveAgent } from "../api";

type Tab = "knowledge" | "tools" | "behavior" | "security";

const WRITE_RISKS = new Set(["medium", "high", "critical"]);

export default function Configure() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    agentId, templateId, coreDraft, catalog, setCatalog,
    selectedKnowledgeIds, setSelectedKnowledgeIds,
    toolSelections, setToolOperations,
    toolDiscovery, setToolDiscovery,
    selectedAudienceIds, setSelectedAudienceIds,
    behavior, setBehavior,
    toolConnections, setToolConnections
  } = useBlueprint();

  const [tab, setTab] = useState<Tab>("knowledge");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [connectingTool, setConnectingTool] = useState<{ id: string; name: string } | null>(null);
  const [expandedToolId, setExpandedToolId] = useState<string | null>(null);
  const [discoveringToolId, setDiscoveringToolId] = useState<string | null>(null);

  const operationsFor = (toolId: string) => toolSelections.find((s) => s.serverId === toolId)?.operations ?? [];

  useEffect(() => {
    if (!coreDraft) return;
    if (catalog && catalog.department === coreDraft.department) return;
    setLoading(true);
    setError(null);
    getCatalogForDepartment(instance, coreDraft.department)
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load the approved catalog"))
      .finally(() => setLoading(false));
  }, [coreDraft, catalog, instance, setCatalog]);

  if (!coreDraft) {
    return (
      <section className="page">
        <h1 className="pageTitle">Configure</h1>
        <div className="notice">Start a new agent, or open a draft from My Agents, first.</div>
        <button className="btn primary" onClick={() => navigate("/start")}>Back to Start</button>
      </section>
    );
  }

  // Expanding a server shows its individual operations instead of selecting
  // the whole integration (requirement: per-operation discovery/selection,
  // grouped by server). An individually-authenticated server that hasn't
  // been connected yet opens the connect form directly — its success
  // response already carries the discovered operations, so there's no
  // separate discovery round trip for that case.
  async function handleToolExpand(t: { id: string; displayName: string; requiresConnection?: boolean }) {
    if (expandedToolId === t.id) {
      setExpandedToolId(null);
      return;
    }
    setExpandedToolId(t.id);
    if (toolDiscovery[t.id]) return; // already discovered or already known to need a connection

    if (t.requiresConnection && !toolConnections[t.id]) {
      setToolDiscovery({ ...toolDiscovery, [t.id]: { toolId: t.id, status: "needs_connection", operations: [] } });
      return;
    }

    setDiscoveringToolId(t.id);
    try {
      const res = await getToolOperations(instance, coreDraft!.department, t.id);
      setToolDiscovery({ ...toolDiscovery, [t.id]: res });
    } catch (e) {
      setToolDiscovery({
        ...toolDiscovery,
        [t.id]: { toolId: t.id, status: "discovery_failed", operations: [], error: e instanceof Error ? e.message : "Discovery failed" },
      });
    } finally {
      setDiscoveringToolId(null);
    }
  }

  function toggleOperation(toolId: string, opName: string, opRisk: string | undefined) {
    const current = operationsFor(toolId);
    const selected = current.includes(opName);
    if (!selected && WRITE_RISKS.has((opRisk ?? "medium").toLowerCase())) {
      if (!window.confirm(`"${opName}" may make changes to business systems (risk: ${opRisk}). Add it?`)) return;
    }
    setToolOperations(toolId, selected ? current.filter((o) => o !== opName) : [...current, opName]);
  }

  function toggle(list: string[], setList: (v: string[]) => void, id: string) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  async function persist() {
    if (!agentId) return;
    setSaving(true);
    try {
      await saveAgent(instance, {
        id: agentId,
        status: "draft",
        coreDraft: coreDraft!,
        knowledgeSourceIds: selectedKnowledgeIds,
        toolSelections,
        audienceIds: selectedAudienceIds,
        behavior,
        templateId: templateId ?? undefined,
      });
    } catch {
      // Best-effort autosave — the user can still continue; Launch re-saves
      // again once the blueprint actually compiles.
    } finally {
      setSaving(false);
    }
  }

  const knowledgeSources = catalog?.knowledgeSources ?? [];
  const tools = catalog?.tools ?? [];
  const audiences = catalog?.audiences ?? [];

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "knowledge", label: "Knowledge", count: selectedKnowledgeIds.length },
    { id: "tools", label: "Tools", count: toolSelections.reduce((n, s) => n + s.operations.length, 0) },
    { id: "behavior", label: "Behavior", count: 0 },
    { id: "security", label: "Security & Audience", count: selectedAudienceIds.length },
  ];

  return (
    <section className="page">
      <p className="eyebrow">CONFIGURE · {coreDraft.department.toUpperCase()}</p>
      <h1 className="pageTitle">{coreDraft.name}</h1>
      <p className="pageIntro">{coreDraft.purpose}</p>

      <div className="tabBar">
        {tabs.map((t) => (
          <button key={t.id} type="button" className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
            {t.count > 0 && <span className="tabCount">{t.count}</span>}
          </button>
        ))}
      </div>

      {loading && <div className="card" style={{ textAlign: "center", padding: 30 }}>Loading approved catalog for {coreDraft.department}…</div>}
      {error && <div className="notice errorNotice">{error}</div>}

      {!loading && tab === "knowledge" && (
        <div className="catalog schematicCard">
          {knowledgeSources.length === 0 && (
            <div className="emptyState"><strong>No approved knowledge sources yet</strong><p>for {coreDraft.department}.</p></div>
          )}
          {knowledgeSources.map((s) => {
            const selected = selectedKnowledgeIds.includes(s.id);
            return (
              <div key={s.id} className="row" style={{ cursor: "pointer" }} onClick={() => toggle(selectedKnowledgeIds, setSelectedKnowledgeIds, s.id)}>
                <span className={`check ${selected ? "on" : ""}`}>{selected ? "✓" : ""}</span>
                <div className="rowMain"><b>{s.displayName}</b><small>Source ID: {s.id}</small></div>
                <span className="pill">Approved</span>
              </div>
            );
          })}
        </div>
      )}

      {!loading && tab === "tools" && (
        <div className="catalog schematicCard">
          {tools.length === 0 && (
            <div className="emptyState"><strong>No approved tools yet</strong><p>for {coreDraft.department}.</p></div>
          )}
          {tools.map((t) => {
            const opsSelected = operationsFor(t.id);
            const connected = !!toolConnections[t.id];
            const expanded = expandedToolId === t.id;
            const discovery = toolDiscovery[t.id];
            return (
              <div key={t.id} className="toolGroup">
                <div className="row" style={{ cursor: "pointer" }} onClick={() => handleToolExpand(t)}>
                  <span className={`check ${opsSelected.length > 0 ? "on" : ""}`}>{opsSelected.length > 0 ? "✓" : ""}</span>
                  <div className="rowMain">
                    <b>{t.displayName}</b>
                    <small>{t.description}</small>
                    {t.capabilities && t.capabilities.length > 0 && (
                      <small>Capabilities: {t.capabilities.join(" · ")}</small>
                    )}
                    <small>
                      {t.kind?.toUpperCase() ?? "TOOL"} ·{" "}
                      {t.accessMode === "read_only" ? "Read only" : "Can make changes"}
                    </small>
                  </div>
                  {opsSelected.length > 0 && <span className="pill">{opsSelected.length} operation(s)</span>}
                  {connected && <span className="pill">Connected</span>}
                  {t.risk && <span className="pill">{t.risk} risk</span>}
                  <span aria-hidden>{expanded ? "▲" : "▼"}</span>
                </div>

                {expanded && (
                  <div className="toolOperations" style={{ paddingLeft: 36, paddingBottom: 12 }}>
                    {discoveringToolId === t.id && <small>Discovering operations on {t.displayName}…</small>}

                    {discovery?.status === "needs_connection" && (
                      <div className="notice">
                        <p>Connect to {t.displayName} to see and select its individual operations.</p>
                        <button
                          type="button"
                          className="btn"
                          onClick={() => setConnectingTool({ id: t.id, name: t.displayName })}
                        >
                          Connect…
                        </button>
                      </div>
                    )}

                    {discovery?.status === "not_configured" && (
                      <div className="notice">
                        Connected — an administrator still needs to enable live operation discovery for{" "}
                        {t.displayName} (declare a connectionheadermap) before individual operations can be listed here.
                      </div>
                    )}

                    {discovery?.status === "discovery_failed" && (
                      <div className="notice errorNotice">
                        Couldn't reach {t.displayName}'s server{discovery.error ? `: ${discovery.error}` : "."}
                      </div>
                    )}

                    {discovery?.status === "discovered" && discovery.operations.length === 0 && (
                      <div className="notice">No operations were returned by {t.displayName}'s server.</div>
                    )}

                    {discovery?.status === "discovered" && discovery.operations.map((op) => {
                      const checked = opsSelected.includes(op.name);
                      return (
                        <label key={op.name} className="ruleRow" style={{ cursor: "pointer" }}>
                          <span>
                            <strong>{op.name}</strong>
                            <small>{op.description}</small>
                          </span>
                          {op.risk && <span className="pill">{op.risk} risk</span>}
                          <input
                            className="toggleCheck"
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleOperation(t.id, op.name, op.risk)}
                            aria-label={`Select operation ${op.name} on ${t.displayName}`}
                          />
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tab === "behavior" && (
        <div className="card schematicCard">
          <label className="field">
            <span className="label">Instructions for the agent</span>
            <textarea
              className="textarea"
              rows={4}
              value={behavior.instructions}
              onChange={(e) => setBehavior({ ...behavior, instructions: e.target.value })}
            />
            <span className="fieldHint">Pre-filled with the generated purpose. Edit freely, or leave as-is.</span>
          </label>
          <div className="field" style={{ marginTop: 18 }}>
            <span className="label">Response detail</span>
            <div className="choiceGrid">
              {(["Concise", "Balanced", "Detailed"] as const).map((style) => (
                <button
                  type="button"
                  key={style}
                  className={`choiceCard ${behavior.responseStyle === style ? "selected" : ""}`}
                  onClick={() => setBehavior({ ...behavior, responseStyle: style })}
                >
                  <strong>{style}</strong>
                  {behavior.responseStyle === style && <span className="selectedMark">Selected</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="behaviorRules">
            <label className="ruleRow">
              <span><strong>Cite knowledge sources</strong><small>Show the source behind policy/procedure answers.</small></span>
              <input className="toggleCheck" type="checkbox" checked={behavior.citeSources}
                onChange={(e) => setBehavior({ ...behavior, citeSources: e.target.checked })} aria-label="Cite knowledge sources" />
            </label>
            <label className="ruleRow">
              <span><strong>Ask clarifying questions</strong><small>When a request is ambiguous or missing detail.</small></span>
              <input className="toggleCheck" type="checkbox" checked={behavior.askClarifyingQuestions}
                onChange={(e) => setBehavior({ ...behavior, askClarifyingQuestions: e.target.checked })} aria-label="Ask clarifying questions" />
            </label>
            <label className="ruleRow">
              <span><strong>Escalate uncertainty</strong><small>Don't guess when approved sources don't support an answer.</small></span>
              <input className="toggleCheck" type="checkbox" checked={behavior.escalateUncertainty}
                onChange={(e) => setBehavior({ ...behavior, escalateUncertainty: e.target.checked })} aria-label="Escalate uncertainty" />
            </label>
          </div>
        </div>
      )}

      {tab === "security" && (
        <div className="catalog schematicCard securityCatalog">
          {audiences.length === 0 && (
            <div className="emptyState"><strong>No audience configured yet</strong><p>for {coreDraft.department}. Contact your administrator.</p></div>
          )}
          {audiences.map((a) => {
            const selected = selectedAudienceIds.includes(a.id);
            return (
              <label key={a.id} className={`audienceRow ${selected ? "isSelected" : ""}`}>
                <span className={`check ${selected ? "on" : ""}`}>{selected ? "✓" : ""}</span>
                <span className="audienceCopy"><strong>{a.id}</strong><small>Enterprise access group</small></span>
                <input type="checkbox" className="visuallyHidden" checked={selected}
                  onChange={() => toggle(selectedAudienceIds, setSelectedAudienceIds, a.id)} aria-label={`Allow ${a.id}`} />
              </label>
            );
          })}
        </div>
      )}

      <div className="pageActions">
        <button className="btn" onClick={() => navigate("/start")}>Back to Start</button>
        <button className="btn" onClick={persist} disabled={saving}>{saving ? "Saving…" : "Save draft"}</button>
        <button
          className="btn primary"
          onClick={async () => { await persist(); navigate("/launch"); }}
          disabled={selectedAudienceIds.length === 0}
        >
          Review &amp; Launch →
        </button>
      </div>
      {connectingTool && (
        <ToolConnectionModal
          toolId={connectingTool.id}
          toolName={connectingTool.name}
          onClose={() => setConnectingTool(null)}
          onConnected={(connectionId, operations, discoveryStatus) => {
            setToolConnections({ ...toolConnections, [connectingTool.id]: connectionId });
            // Operations discovered live with the credentials just submitted
            // (tool_connections.create_tool_connection) — the user still has
            // to pick which ones the agent gets; connecting alone selects none.
            setToolDiscovery({
              ...toolDiscovery,
              [connectingTool.id]: {
                toolId: connectingTool.id,
                status: discoveryStatus === "discovered" ? "discovered" : discoveryStatus,
                operations,
              },
            });
            setExpandedToolId(connectingTool.id);
            setConnectingTool(null);
          }}
        />
      )}
    </section>
  );
}
