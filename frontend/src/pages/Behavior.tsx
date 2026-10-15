import { useNavigate } from "react-router-dom";
import { useBlueprint } from "../BlueprintContext";

export default function Behavior() {
  const navigate = useNavigate();
  const { coreDraft, behavior, setBehavior } = useBlueprint();
  if (!coreDraft) return <section className="page"><h1 className="pageTitle">Behavior</h1><div className="notice">Start on Describe to configure an agent.</div><button className="btn primary" onClick={() => navigate("/describe")}>Back to Describe</button></section>;
  const update = (changes: Partial<typeof behavior>) => setBehavior({ ...behavior, ...changes });
  return <section className="page">
    <p className="eyebrow">AGENT CONFIGURATION · STEP 5 OF 10</p>
    <h1 className="pageTitle">Shape your agent’s behavior</h1>
    <p className="pageIntro">Set the response style and operating principles for <strong>{coreDraft.name}</strong>. These preferences are included in the review summary; runtime enforcement still needs to be wired into the agent deployment.</p>
    <div className="card">
      <label className="field"><span className="label">Instructions for the agent</span><textarea className="textarea" rows={5} value={behavior.instructions} onChange={e => update({ instructions: e.target.value })} placeholder="Describe how the agent should work, what it should avoid, and when it should ask for help." /><span className="fieldHint">Be specific about scope, approved sources, and actions it must not take.</span></label>
      <div className="field" style={{ marginTop: 22 }}><span className="label">Response detail</span><div className="choiceGrid">{(["Concise", "Balanced", "Detailed"] as const).map((style, i) => <button type="button" key={style} className={`choiceCard ${behavior.responseStyle === style ? "selected" : ""}`} onClick={() => update({ responseStyle: style })}><span className="choiceIcon">{["↗", "☷", "≡"][i]}</span><strong>{style}</strong><small>{["Key answer first", "Clear answer with useful context", "More explanation and steps"][i]}</small>{behavior.responseStyle === style && <span className="selectedMark">Selected</span>}</button>)}</div></div>
    </div>
    <div className="card behaviorRules"><h2 className="sectionTitle">Reliability rules</h2><p className="pageIntro compact">Choose how the agent should handle uncertainty and source-backed answers.</p>
      <label className="ruleRow"><span><strong>Cite knowledge sources</strong><small>Make it easier for users to verify answers.</small></span><input className="toggleCheck" type="checkbox" checked={behavior.citeSources} onChange={e => update({ citeSources: e.target.checked })} /></label>
      <label className="ruleRow"><span><strong>Ask clarifying questions</strong><small>Ask when a request is ambiguous or missing key details.</small></span><input className="toggleCheck" type="checkbox" checked={behavior.askClarifyingQuestions} onChange={e => update({ askClarifyingQuestions: e.target.checked })} /></label>
      <label className="ruleRow"><span><strong>Escalate uncertainty</strong><small>Do not guess when approved sources do not support an answer.</small></span><input className="toggleCheck" type="checkbox" checked={behavior.escalateUncertainty} onChange={e => update({ escalateUncertainty: e.target.checked })} /></label>
    </div>
    <div className="notice warn">Behavior preferences are currently saved in this browser session and shown in Review. They are not yet sent to the Foundry runtime payload.</div>
    <div className="pageActions"><button className="btn" onClick={() => navigate("/tools")}>Back</button><button className="btn primary" onClick={() => navigate("/security")}>Continue to Security <span aria-hidden="true">→</span></button></div>
  </section>;
}
