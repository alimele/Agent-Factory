import { useNavigate } from "react-router-dom";
import { useBlueprint } from "../BlueprintContext";
import { CoreBlueprintDraft } from "../api";

const AGENT_TYPES = ["Knowledge Assistant", "Analyst", "Process Agent", "Action Agent", "Monitoring Agent"];
const DATA_CLASSIFICATIONS = ["Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted"];

export default function ContextPage() {
  const navigate = useNavigate();
  const { coreDraft, setCoreDraft } = useBlueprint();

  if (!coreDraft) return <section className="page"><p className="eyebrow">AGENT CONFIGURATION</p><h1 className="pageTitle">Define the context</h1><div className="notice">Start on Describe to generate an agent draft first.</div><button className="btn primary" onClick={() => navigate("/describe")}>Back to Describe</button></section>;

  const draft: CoreBlueprintDraft = coreDraft;
  function update<K extends keyof CoreBlueprintDraft>(key: K, value: CoreBlueprintDraft[K]) {
    setCoreDraft({ ...draft, [key]: value });
  }

  return <section className="page">
    <p className="eyebrow">AGENT CONFIGURATION · STEP 2 OF 10</p>
    <h1 className="pageTitle">Define the context</h1>
    <p className="pageIntro">Review the details inferred from your description. These define the agent’s purpose and the sensitivity of the information it may handle.</p>
    <div className="card formCard">
      <div className="formGrid">
        <label className="field"><span className="label">Agent name</span><input className="input" value={draft.name} onChange={e => update("name", e.target.value)} placeholder="e.g. IT Support Assistant" /></label>
        <label className="field"><span className="label">Department</span><input className="input" value={draft.department} disabled title="Set from the initial description" /><span className="fieldHint">To change the department, update the initial description.</span></label>
        <label className="field"><span className="label">Agent type</span><select className="select" value={draft.agentType} onChange={e => update("agentType", e.target.value)}>{AGENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select></label>
        <label className="field"><span className="label">Data classification</span><select className="select" value={draft.dataClassification} onChange={e => update("dataClassification", e.target.value)}>{DATA_CLASSIFICATIONS.map(d => <option key={d} value={d}>{d}</option>)}</select><span className="fieldHint">Choose the highest sensitivity of data this agent may process.</span></label>
        <label className="field full"><span className="label">Purpose and responsibilities</span><textarea className="textarea" rows={4} value={draft.purpose} onChange={e => update("purpose", e.target.value)} placeholder="Describe what the agent should help users accomplish." /></label>
      </div>
    </div>
    <div className="card optionCard"><div><strong>Require human approval for actions</strong><p className="fieldHint">Keep a person in control before the agent performs actions.</p></div><input className="toggleCheck" type="checkbox" checked={draft.humanApproval} onChange={e => update("humanApproval", e.target.checked)} aria-label="Require human approval for actions" /></div>
    <div className="notice">These selections are checked again by the backend when the blueprint is compiled.</div>
    <div className="pageActions"><button className="btn" onClick={() => navigate("/describe")}>Back</button><button className="btn primary" onClick={() => navigate("/knowledge")} disabled={!draft.name.trim() || !draft.purpose.trim()}>Continue to Knowledge <span aria-hidden="true">→</span></button></div>
  </section>;
}
