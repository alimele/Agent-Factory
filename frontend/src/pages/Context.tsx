import { useNavigate } from "react-router-dom";
import { useBlueprint } from "../BlueprintContext";
import { CoreBlueprintDraft } from "../api";

// All the catalog-bound fields here (department, agentType, pattern,
// modelPolicy, dataClassification) are rendered as <select>s constrained to
// the same catalog values the backend used — editing them client-side is
// fine for UX, since blueprint/compile re-validates every one of these
// server-side before anything is trusted (see blueprint_compiler.py).
const AGENT_TYPES = ["Knowledge Assistant", "Analyst", "Process Agent", "Action Agent", "Monitoring Agent"];
const DATA_CLASSIFICATIONS = ["Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted"];

export default function ContextPage() {
  const navigate = useNavigate();
  const { coreDraft, setCoreDraft } = useBlueprint();

  if (!coreDraft) {
    return (
      <div>
        <h2>Context</h2>
        <p>Go back to Describe first — nothing's been generated yet.</p>
        <button onClick={() => navigate("/describe")}>Back to Describe</button>
      </div>
    );
  }

  // TS can't narrow `coreDraft` as non-null inside this closure on its own
  // (it's component state, not a local const) — the early return above
  // guarantees it at runtime, so we assert it here rather than re-checking.
  const draft = coreDraft as CoreBlueprintDraft;

  function update<K extends keyof CoreBlueprintDraft>(key: K, value: CoreBlueprintDraft[K]) {
    setCoreDraft({ ...draft, [key]: value });
  }

  return (
    <div>
      <h2>Context</h2>
      <p>Here's what we understood from your description — review and adjust anything that's off.</p>

      <label>
        Agent name
        <input value={coreDraft.name} onChange={(e) => update("name", e.target.value)} />
      </label>
      <br />

      <label>
        Department
        <input value={coreDraft.department} disabled title="Set by Describe — go back to change it" />
      </label>
      <br />

      <label>
        Agent type
        <select value={coreDraft.agentType} onChange={(e) => update("agentType", e.target.value)}>
          {AGENT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
      <br />

      <label>
        Purpose
        <textarea value={coreDraft.purpose} onChange={(e) => update("purpose", e.target.value)} rows={3} />
      </label>
      <br />

      <label>
        Data classification
        <select
          value={coreDraft.dataClassification}
          onChange={(e) => update("dataClassification", e.target.value)}
        >
          {DATA_CLASSIFICATIONS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>
      <br />

      <label>
        <input
          type="checkbox"
          checked={coreDraft.humanApproval}
          onChange={(e) => update("humanApproval", e.target.checked)}
        />
        Require human approval before this agent's actions run
      </label>

      <div style={{ marginTop: 12 }}>
        <button onClick={() => navigate("/knowledge")}>Next: Knowledge</button>
      </div>
    </div>
  );
}
