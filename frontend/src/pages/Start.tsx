import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint, defaultBehavior } from "../BlueprintContext";
import { AgentTemplate, generateCoreBlueprint, listTemplates, saveAgent } from "../api";

export default function Start() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    description, setDescription, setCoreDraft, setBehavior,
    setAgentId, setTemplateId, resetForNewAgent,
  } = useBlueprint();

  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [customOpen, setCustomOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTemplates(instance)
      .then(setTemplates)
      .catch((e) => setTemplatesError(e instanceof Error ? e.message : "Failed to load the solution catalog."))
      .finally(() => setTemplatesLoading(false));
  }, [instance]);

  async function persistDraft(
    draft: Parameters<typeof setCoreDraft>[0],
    templateId: string | null
  ) {
    const saved = await saveAgent(instance, {
      status: "draft",
      coreDraft: draft!,
      knowledgeSourceIds: [],
      toolIds: [],
      audienceIds: [],
      behavior: { ...defaultBehavior, instructions: draft!.purpose },
      templateId: templateId ?? undefined,
    });
    setAgentId(saved.id);
  }

  async function startFromTemplate(t: AgentTemplate) {
    if (starting) return;
    setStarting(true);
    setError(null);
    resetForNewAgent();
    const draft = {
      name: t.displayName,
      department: t.department,
      agentType: t.agentType,
      pattern: t.pattern,
      purpose: t.purpose,
      modelPolicy: t.modelPolicy,
      dataClassification: t.dataClassification,
      humanApproval: t.humanApproval,
      externalSharing: t.externalSharing,
    };
    setCoreDraft(draft);
    setTemplateId(t.id);
    setBehavior({ ...defaultBehavior, instructions: draft.purpose });
    try {
      await persistDraft(draft, t.id);
      navigate("/configure");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start this agent.");
    } finally {
      setStarting(false);
    }
  }

  async function startFromDescription() {
    if (!description.trim()) {
      setError("Describe what you'd like your agent to do first.");
      return;
    }
    setStarting(true);
    setError(null);
    resetForNewAgent();
    setDescription(description);
    try {
      const draft = await generateCoreBlueprint(instance, description);
      setCoreDraft(draft);
      setBehavior({ ...defaultBehavior, instructions: draft.purpose });
      await persistDraft(draft, null);
      navigate("/configure");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong generating the blueprint.");
    } finally {
      setStarting(false);
    }
  }

  const grouped = templates.reduce<Record<string, AgentTemplate[]>>((acc, t) => {
    (acc[t.department] ??= []).push(t);
    return acc;
  }, {});

  return (
    <section className="page">
      <p className="eyebrow">NEW AGENT</p>
      <h1 className="pageTitle">What would you like to automate?</h1>
      <p className="pageIntro">
        Start from a ready-made solution for your department, or describe a custom agent in your own words.
        Either way, you'll still choose the exact approved knowledge sources, tools, and audience yourself on the next step.
      </p>

      {templatesLoading && (
        <div className="card" style={{ textAlign: "center", padding: 30 }}>Loading solution catalog…</div>
      )}
      {templatesError && <div className="notice errorNotice">{templatesError}</div>}

      {!templatesLoading && !templatesError && templates.length === 0 && (
        <div className="emptyState">
          <strong>No ready-made solutions yet for your department</strong>
          <p>Describe a custom agent below instead.</p>
        </div>
      )}

      {Object.entries(grouped).map(([dept, items]) => (
        <div key={dept} className="templateGroup">
          <h2 className="sectionTitle">{dept}</h2>
          <div className="templateGrid">
            {items.map((t) => (
              <button
                key={t.id}
                type="button"
                className="templateCard schematicCard"
                onClick={() => startFromTemplate(t)}
                disabled={starting}
              >
                <span className="templateIcon">{t.icon || t.department.slice(0, 2).toUpperCase()}</span>
                <strong>{t.displayName}</strong>
                <small>{t.description || t.purpose}</small>
                <span className="pill">{t.department}</span>
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="card schematicCard" style={{ marginTop: 24 }}>
        <button type="button" className="textButton" onClick={() => setCustomOpen((o) => !o)}>
          {customOpen ? "Hide custom description" : "+ Describe a custom agent instead"}
        </button>
        {customOpen && (
          <div style={{ marginTop: 14 }}>
            <label className="label">Agent purpose</label>
            <textarea
              className="textarea"
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. An agent that answers employee questions about leave policy and can raise a ServiceNow request when they need HR support."
              disabled={starting}
            />
            <div style={{ marginTop: 14 }}>
              <button className="btn primary" onClick={startFromDescription} disabled={starting}>
                {starting ? "Generating…" : "Generate blueprint →"}
              </button>
            </div>
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
