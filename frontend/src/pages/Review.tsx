import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { compileBlueprint } from "../api";
import { callPolicyEvaluate } from "../callPolicyEvaluate";

interface CheckResult { id: string; name: string; status: "pass" | "fail" | "flagged" | "skipped"; reason: string }
interface PolicyEvaluation { overall_status: "pass" | "fail" | "flagged"; risk_tier: "low" | "medium" | "high" | "restricted"; required_approvers: string[]; checks: CheckResult[] }

function SummaryCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="summaryCard"><span>{label}</span><strong>{value || "Not specified"}</strong>{detail && <small>{detail}</small>}</div>;
}

export default function Review() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { coreDraft, selectedKnowledgeIds, selectedToolIds, selectedAudienceIds, behavior, compileResult, setCompileResult } = useBlueprint();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [policyResult, setPolicyResult] = useState<PolicyEvaluation | null>(null);

  if (!coreDraft) return <section className="page"><h1 className="pageTitle">Review blueprint</h1><div className="notice">Go back to Describe to create an agent draft first.</div><button className="btn primary" onClick={() => navigate("/describe")}>Back to Describe</button></section>;
  const draft = coreDraft;

  async function handleCompile() {
    setLoading(true); setError(null); setPolicyResult(null);
    try {
      const result = await compileBlueprint(instance, { coreDraft: draft, knowledgeSourceIds: selectedKnowledgeIds, toolIds: selectedToolIds, audienceIds: selectedAudienceIds });
      setCompileResult(result);
    } catch (e) { setError(e instanceof Error ? e.message : "Blueprint compilation failed."); }
    finally { setLoading(false); }
  }

  async function handlePolicyCheck() {
    if (!compileResult) return;
    setPolicyLoading(true); setPolicyError(null);
    try {
      const evaluation = await callPolicyEvaluate(instance, { blueprint: compileResult.blueprint, stage: "pre_deploy" });
      setPolicyResult(evaluation);
    } catch (e) { setPolicyError(e instanceof Error ? e.message : "Policy evaluation failed."); }
    finally { setPolicyLoading(false); }
  }

  return <section className="page">
    <p className="eyebrow">AGENT CONFIGURATION · STEP 7 OF 10</p>
    <h1 className="pageTitle">Review your blueprint</h1>
    <p className="pageIntro">Check the configuration before generating the blueprint and running the pre-deployment policy evaluation.</p>

    <div className="reviewSection"><div className="sectionHeading"><div><h2 className="sectionTitle">Agent overview</h2><p className="pageIntro compact">The core details from your configuration.</p></div><button className="textButton" onClick={() => navigate("/context")}>Edit details</button></div>
      <div className="summaryGrid"><SummaryCard label="Agent name" value={draft.name} detail={draft.department} /><SummaryCard label="Agent type" value={draft.agentType} detail={draft.pattern.replace(/_/g, " ")} /><SummaryCard label="Data classification" value={draft.dataClassification} detail={draft.humanApproval ? "Human approval required" : "No human approval requirement"} /><SummaryCard label="Model policy" value={draft.modelPolicy} detail="Approved policy selection" /></div>
      <div className="card reviewPurpose"><span className="label">Purpose</span><p>{draft.purpose}</p></div>
    </div>

    <div className="reviewSection"><div className="sectionHeading"><div><h2 className="sectionTitle">Connected resources</h2><p className="pageIntro compact">Selected catalog entries and who can access the agent.</p></div><button className="textButton" onClick={() => navigate("/knowledge")}>Edit resources</button></div>
      <div className="resourceGrid"><div className="resourceCard"><div className="resourceHead"><span className="resourceIcon">▤</span><span className="pill">{selectedKnowledgeIds.length} selected</span></div><strong>Knowledge sources</strong>{selectedKnowledgeIds.length ? <ul>{selectedKnowledgeIds.map(id => <li key={id}>{id}</li>)}</ul> : <p className="mutedText">No knowledge sources selected.</p>}</div>
      <div className="resourceCard"><div className="resourceHead"><span className="resourceIcon">⚙</span><span className="pill">{selectedToolIds.length} selected</span></div><strong>Tools and actions</strong>{selectedToolIds.length ? <ul>{selectedToolIds.map(id => <li key={id}>{id}</li>)}</ul> : <p className="mutedText">No tools selected.</p>}</div>
      <div className="resourceCard"><div className="resourceHead"><span className="resourceIcon">♙</span><span className="pill">{selectedAudienceIds.length} selected</span></div><strong>Authorized audiences</strong>{selectedAudienceIds.length ? <ul>{selectedAudienceIds.map(id => <li key={id}>{id}</li>)}</ul> : <p className="mutedText">No audience selected.</p>}</div></div>
    </div>

    <div className="reviewSection"><div className="sectionHeading"><div><h2 className="sectionTitle">Behavior preferences</h2><p className="pageIntro compact">Response guidance selected on the Behavior page.</p></div><button className="textButton" onClick={() => navigate("/behavior")}>Edit behavior</button></div>
      <div className="card behaviorReview"><div><span className="label">Response detail</span><strong>{behavior.responseStyle}</strong></div><div><span className="label">Reliability rules</span><p>{[behavior.citeSources && "Cite sources", behavior.askClarifyingQuestions && "Ask clarifying questions", behavior.escalateUncertainty && "Escalate uncertainty"].filter(Boolean).join(" · ") || "No optional rules enabled"}</p></div><div><span className="label">Instructions</span><p>{behavior.instructions || "No additional instructions."}</p></div></div>
      <div className="notice warn">Behavior preferences are currently a frontend draft and are not included in the backend Foundry payload yet.</div>
    </div>

    <div className="card compilePanel"><div className="compileIcon">✓</div><div className="compileCopy"><h2 className="sectionTitle">Generate blueprint</h2><p className="pageIntro compact">The backend validates the catalog-bound fields and compiles the selected configuration.</p></div><button className="btn primary" onClick={handleCompile} disabled={loading || !draft.name.trim() || !draft.purpose.trim() || selectedAudienceIds.length === 0}>{loading ? "Generating…" : compileResult ? "Regenerate blueprint" : "Generate blueprint"}</button></div>
    {error && <div className="notice errorNotice">{error}</div>}

    {compileResult && <div className="reviewSection resultSection"><div className="sectionHeading"><div><h2 className="sectionTitle">Blueprint generated</h2><p className="pageIntro compact">Your configuration has been compiled successfully. Review the policy checks before proceeding.</p></div><span className="statusPill success">Compiled</span></div>
      <div className="card policyPanel"><div><h3>Pre-deployment policy check</h3><p className="pageIntro compact">Evaluate the compiled blueprint against the current policy service.</p></div><button className="btn primary" onClick={handlePolicyCheck} disabled={policyLoading}>{policyLoading ? "Checking policy…" : "Run policy check"}</button></div>
      {policyError && <div className="notice errorNotice">{policyError}</div>}
      {policyResult && <div className={`policyResult ${policyResult.overall_status}`}><div className="policyResultHead"><strong>{policyResult.overall_status === "pass" ? "Policy check passed" : policyResult.overall_status === "fail" ? "Policy check blocked" : "Policy review required"}</strong><span className="pill">Risk: {policyResult.risk_tier}</span></div>{policyResult.required_approvers.length > 0 && <p>Required approvers: {policyResult.required_approvers.join(", ")}</p>}<div className="checkList">{policyResult.checks.map(check => <div className="checkResult" key={check.id}><span className={`checkStatus ${check.status}`}>{check.status === "pass" ? "✓" : check.status === "fail" ? "!" : check.status === "flagged" ? "⚑" : "–"}</span><div><strong>{check.name}</strong><p>{check.reason}</p></div><span className="pill">{check.status}</span></div>)}</div>{policyResult.overall_status !== "fail" && <div className="notice warn">The policy check does not create or publish an agent. Foundry dev/test agent creation is not wired up yet (Phase 4).</div>}</div>}
      <details className="technicalDetails"><summary>Technical details (JSON)</summary><p className="fieldHint">Use these payloads for debugging. They are not required for normal review.</p><h3>Compiled blueprint</h3><pre>{JSON.stringify(compileResult.blueprint, null, 2)}</pre><h3>Foundry payload</h3><pre>{JSON.stringify(compileResult.foundryPayload, null, 2)}</pre></details>
    </div>}
    <div className="pageActions"><button className="btn" onClick={() => navigate("/security")}>Back</button>{compileResult && <button className="btn primary" onClick={() => navigate("/test")} disabled={policyResult?.overall_status === "fail"}>Continue to Test <span aria-hidden="true">→</span></button>}</div>
  </section>;
}
