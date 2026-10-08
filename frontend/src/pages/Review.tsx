import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { compileBlueprint } from "../api";
import { callPolicyEvaluate } from "../callPolicyEvaluate";

interface CheckResult {
  id: string;
  name: string;
  status: "pass" | "fail" | "flagged" | "skipped";
  reason: string;
}

interface PolicyEvaluation {
  overall_status: "pass" | "fail" | "flagged";
  risk_tier: "low" | "medium" | "high" | "restricted";
  required_approvers: string[];
  checks: CheckResult[];
}

export default function Review() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    coreDraft,
    selectedKnowledgeIds,
    selectedToolIds,
    selectedAudienceIds,
    compileResult,
    setCompileResult,
  } = useBlueprint();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [policyLoading, setPolicyLoading] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [policyResult, setPolicyResult] = useState<PolicyEvaluation | null>(null);

  if (!coreDraft) {
    return (
      <div>
        <h2>Review</h2>
        <p>Go back to Describe first.</p>
        <button onClick={() => navigate("/describe")}>Back to Describe</button>
      </div>
    );
  }

  async function handleCompile() {
    setLoading(true);
    setError(null);
    setPolicyResult(null); // a re-compiled blueprint invalidates any prior policy check
    try {
      const result = await compileBlueprint(instance, {
        coreDraft: coreDraft!,
        knowledgeSourceIds: selectedKnowledgeIds,
        toolIds: selectedToolIds,
        audienceIds: selectedAudienceIds,
      });
      setCompileResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Compile failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateAgent() {
    if (!compileResult) return;
    setPolicyLoading(true);
    setPolicyError(null);
    try {
      const evaluation = await callPolicyEvaluate(instance, {
        blueprint: compileResult.blueprint,
        stage: "pre_deploy",
      });
      setPolicyResult(evaluation);

      if (evaluation.overall_status === "fail") return; // blocked — show failed checks, stop here

      // PASS or FLAGGED: policy cleared. Actual Foundry dev/test agent
      // creation is Phase 4 — not built yet. TODO (Phase 4): replace this
      // with the real "create Foundry dev/test agent" call, and on success
      // call setAgentCreated(true) from BlueprintContext.
    } catch (e) {
      setPolicyError(e instanceof Error ? e.message : "Policy evaluation failed.");
    } finally {
      setPolicyLoading(false);
    }
  }

  return (
    <div>
      <h2>Review</h2>
      <p>Everything collected so far — generate the final blueprint, then submit it for policy evaluation.</p>

      <ul>
        <li><strong>Name:</strong> {coreDraft.name}</li>
        <li><strong>Department:</strong> {coreDraft.department}</li>
        <li><strong>Agent type:</strong> {coreDraft.agentType}</li>
        <li><strong>Purpose:</strong> {coreDraft.purpose}</li>
        <li><strong>Data classification:</strong> {coreDraft.dataClassification}</li>
        <li><strong>Knowledge sources:</strong> {selectedKnowledgeIds.join(", ") || "none"}</li>
        <li><strong>Tools:</strong> {selectedToolIds.join(", ") || "none"}</li>
        <li><strong>Audience:</strong> {selectedAudienceIds.join(", ") || "none"}</li>
      </ul>

      <button onClick={handleCompile} disabled={loading}>
        {loading ? "Compiling…" : "Generate Blueprint"}
      </button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {compileResult && (
        <div style={{ marginTop: 16 }}>
          <h3>Generated Blueprint</h3>
          <pre style={{ background: "#f7f9fc", padding: 12, overflowX: "auto" }}>
            {JSON.stringify(compileResult.blueprint, null, 2)}
          </pre>

          <h3>Foundry Agent Payload</h3>
          <pre style={{ background: "#f7f9fc", padding: 12, overflowX: "auto" }}>
            {JSON.stringify(compileResult.foundryPayload, null, 2)}
          </pre>

          <button onClick={handleCreateAgent} disabled={policyLoading}>
            {policyLoading ? "Checking policy…" : "Create Agent"}
          </button>
          {policyError && <p style={{ color: "crimson" }}>{policyError}</p>}

          {policyResult && (
            <div style={{ marginTop: 16 }}>
              {policyResult.overall_status === "fail" && (
                <div style={{ color: "crimson" }}>
                  <p><strong>Blocked — policy check failed:</strong></p>
                  <ul>
                    {policyResult.checks
                      .filter((c) => c.status === "fail")
                      .map((c) => <li key={c.id}>{c.name}: {c.reason}</li>)}
                  </ul>
                </div>
              )}

              {policyResult.overall_status === "flagged" && (
                <div style={{ color: "#a86700" }}>
                  <p>
                    <strong>Flagged</strong> — risk tier: {policyResult.risk_tier}, routed to:{" "}
                    {policyResult.required_approvers.join(", ")}
                  </p>
                  <ul>
                    {policyResult.checks
                      .filter((c) => c.status === "flagged")
                      .map((c) => <li key={c.id}>{c.name}: {c.reason}</li>)}
                  </ul>
                </div>
              )}

              {policyResult.overall_status === "pass" && (
                <div style={{ color: "#16865b" }}>
                  <p>
                    <strong>Policy check passed</strong> — risk tier: {policyResult.risk_tier}.
                    Agent creation (Foundry dev/test) isn't wired up yet — coming in Phase 4.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
