import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { compileBlueprint, createTestAgent, runTestAgent, saveAgent } from "../api";
import { callPolicyEvaluate } from "../callPolicyEvaluate";

interface CheckResult { id: string; name: string; status: "pass" | "fail" | "flagged" | "skipped"; reason: string }
interface PolicyEvaluation {
  overall_status: "pass" | "fail" | "flagged";
  risk_tier: "low" | "medium" | "high" | "restricted";
  required_approvers: string[];
  checks: CheckResult[];
}

export default function ReviewLaunch() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    agentId, templateId, coreDraft, selectedKnowledgeIds, selectedToolIds, selectedAudienceIds,
    behavior, createdAgent, setCreatedAgent,
  } = useBlueprint();

  const [busy, setBusy] = useState<"launch" | "test" | null>(null);
  const [stage, setStage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [policyResult, setPolicyResult] = useState<PolicyEvaluation | null>(null);
  const [prompt, setPrompt] = useState("Without calling any tools, describe your purpose and operating rules.");
  const [output, setOutput] = useState<string | null>(null);

  if (!coreDraft) {
    return (
      <section className="page">
        <h1 className="pageTitle">Review &amp; Launch</h1>
        <div className="notice">Start a new agent, or open a draft from My Agents, first.</div>
        <button className="btn primary" onClick={() => navigate("/start")}>Back to Start</button>
      </section>
    );
  }

  async function runPipeline() {
    setError(null);
    setPolicyResult(null);
    setBusy("launch");
    try {
      setStage("Compiling blueprint…");
      const compiled = await compileBlueprint(instance, {
        coreDraft: coreDraft!, knowledgeSourceIds: selectedKnowledgeIds, toolIds: selectedToolIds,
        audienceIds: selectedAudienceIds, behavior,
      });

      setStage("Running the governance policy gate…");
      const evaluation = await callPolicyEvaluate(instance, { blueprint: compiled.blueprint, stage: "pre_deploy" });
      setPolicyResult(evaluation);

      if (agentId) {
        await saveAgent(instance, {
          id: agentId, status: "compiled", coreDraft: coreDraft!,
          knowledgeSourceIds: selectedKnowledgeIds, toolIds: selectedToolIds, audienceIds: selectedAudienceIds,
          behavior, blueprint: compiled.blueprint, foundryPayload: compiled.foundryPayload,
          policyEvaluation: evaluation, templateId: templateId ?? undefined,
        });
      }

      if (evaluation.overall_status !== "fail") {
        setStage("Creating the development agent in Foundry…");
        const response = await createTestAgent(instance, {
          coreDraft: coreDraft!, knowledgeSourceIds: selectedKnowledgeIds, toolIds: selectedToolIds,
          audienceIds: selectedAudienceIds, behavior,
        });
        setCreatedAgent(response.agent);
        if (agentId) {
          await saveAgent(instance, {
            id: agentId, status: "dev_created", coreDraft: coreDraft!,
            knowledgeSourceIds: selectedKnowledgeIds, toolIds: selectedToolIds, audienceIds: selectedAudienceIds,
            behavior, blueprint: compiled.blueprint, foundryPayload: compiled.foundryPayload,
            policyEvaluation: evaluation, templateId: templateId ?? undefined,
            foundryAgentName: response.agent.name, foundryAgentVersion: response.agent.version,
          });
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "The launch pipeline failed.");
    } finally {
      setBusy(null);
      setStage("");
    }
  }

  async function handleTest() {
    if (!createdAgent) return;
    setBusy("test");
    setOutput(null);
    setError(null);
    try {
      const result = await runTestAgent(instance, { agentName: createdAgent.name, agentVersion: createdAgent.version, prompt });
      setOutput(result.outputText);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The test prompt failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page">
      <p className="eyebrow">REVIEW &amp; LAUNCH</p>
      <h1 className="pageTitle">{coreDraft.name}</h1>

      <div className="summaryGrid">
        <div className="summaryCard"><span>Department</span><strong>{coreDraft.department}</strong></div>
        <div className="summaryCard"><span>Knowledge</span><strong>{selectedKnowledgeIds.length} source(s)</strong></div>
        <div className="summaryCard"><span>Tools</span><strong>{selectedToolIds.length} tool(s)</strong></div>
        <div className="summaryCard"><span>Audience</span><strong>{selectedAudienceIds.length} group(s)</strong></div>
      </div>
      <div className="card reviewPurpose"><span className="label">Purpose</span><p>{coreDraft.purpose}</p></div>

      <div className="card compilePanel schematicCard">
        <div className="compileIcon">▶</div>
        <div className="compileCopy">
          <h2 className="sectionTitle">Compile, validate &amp; create dev agent</h2>
          <p className="pageIntro compact">Re-validates everything against the live catalogs, runs the governance gate, and — if it doesn't fail — creates an unpublished Foundry development agent. One step.</p>
        </div>
        <button className="btn primary" onClick={runPipeline} disabled={busy !== null}>
          {busy === "launch" ? (stage || "Working…") : "Compile & Launch"}
        </button>
      </div>
      {error && <div className="notice errorNotice">{error}</div>}

      {policyResult && (
        <div className={`policyResult ${policyResult.overall_status}`}>
          <div className="policyResultHead">
            <strong>
              {policyResult.overall_status === "pass" ? "Policy check passed"
                : policyResult.overall_status === "fail" ? "Policy check blocked" : "Policy review required"}
            </strong>
            <span className="pill">Risk: {policyResult.risk_tier}</span>
          </div>
          {policyResult.required_approvers.length > 0 && (
            <p>Required approvers: {policyResult.required_approvers.join(", ")}</p>
          )}
          <div className="checkList">
            {policyResult.checks.map((c) => (
              <div className="checkResult" key={c.id}>
                <span className={`checkStatus ${c.status}`}>
                  {c.status === "pass" ? "✓" : c.status === "fail" ? "!" : c.status === "flagged" ? "⚑" : "–"}
                </span>
                <div><strong>{c.name}</strong><p>{c.reason}</p></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {createdAgent && (
        <div className="reviewSection">
          <h2 className="sectionTitle">Test the development agent</h2>
          <div className="card schematicCard">
            <textarea className="textarea" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
            <div className="pageActions">
              <span className="pill">{createdAgent.name} · v{createdAgent.version}</span>
              <button className="btn primary" onClick={handleTest} disabled={busy !== null}>
                {busy === "test" ? "Running…" : "Run test prompt"}
              </button>
            </div>
          </div>
          {output !== null && <div className="card" style={{ marginTop: 14 }}><pre className="testOutput">{output}</pre></div>}
          <div className="notice warn">
            This sends a real prompt to Foundry. An attached action tool may call its connected API —
            use read-only or sandboxed tools while testing. This agent is unpublished and only you can test it;
            find it anytime from My Agents or Playground.
          </div>
        </div>
      )}

      <div className="pageActions">
        <button className="btn" onClick={() => navigate("/configure")}>Back to Configure</button>
        <button className="btn" onClick={() => navigate("/my-agents")}>Go to My Agents</button>
      </div>
    </section>
  );
}
