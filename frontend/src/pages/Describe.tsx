import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint, defaultBehavior } from "../BlueprintContext";
import { generateCoreBlueprint } from "../api";

export default function Describe() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { description, setDescription, setCoreDraft,setCatalog, 
    setSelectedKnowledgeIds, setSelectedToolIds, setSelectedAudienceIds, 
    setCompileResult, setBehavior } = useBlueprint();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  


  async function handleSubmit() {
    if (!description.trim()) {
      setError("Describe what you'd like your agent to do first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const draft = await generateCoreBlueprint(instance, description);
      setCoreDraft(draft);
      setCatalog(null);
      setSelectedKnowledgeIds([]);
      setSelectedToolIds([]);
      setSelectedAudienceIds([]);
      setCompileResult(null);
      // Pre-fill the Behavior page's instructions box with the generated
      // purpose, so the user has something concrete to edit instead of a
      // blank box or a generic placeholder. If they never touch it, this
      // is exactly what gets sent (see instructions.py's dedupe-against-
      // purpose logic); if they edit it, their edit is what's sent.
      setBehavior({ ...defaultBehavior, instructions: draft.purpose });
      navigate("/context");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong generating the blueprint.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="eyebrow" style={{ fontSize: 10, color: "var(--brand)", fontWeight: 800, letterSpacing: ".1em", textTransform: "uppercase" }}>
        Step 1 of 10 · Describe
      </div>
      <h1 style={{ fontSize: 26, margin: "7px 0 8px" }}>What would you like your agent to do?</h1>
      <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.6, maxWidth: 560, margin: "0 0 24px" }}>
        Start with the business outcome, in plain language. Everything else unlocks once you submit this.
      </p>

      <label className="label">Agent purpose</label>
      <textarea
        className="textarea"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={6}
        placeholder="e.g. An agent that answers employee questions about leave policy and can raise a ServiceNow request when they need HR support."
        disabled={loading}
      />

      <div style={{ marginTop: 18 }}>
        <button className="btn primary" onClick={handleSubmit} disabled={loading}>
          {loading ? "Generating…" : "Submit description — unlock the rest →"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
