import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { compileBlueprint } from "../api";

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

  return (
    <div>
      <h2>Review</h2>
      <p>Everything collected so far — generate the final blueprint before submitting for approval.</p>

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

          <button onClick={() => navigate("/submit")}>Next: Submit for approval</button>
        </div>
      )}
    </div>
  );
}
