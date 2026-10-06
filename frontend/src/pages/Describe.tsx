import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { generateCoreBlueprint } from "../api";

export default function Describe() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { description, setDescription, setCoreDraft } = useBlueprint();
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
      navigate("/context");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong generating the blueprint.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Describe</h2>
      <p>What would you like your agent to do?</p>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={6}
        style={{ width: "100%", maxWidth: 600 }}
        placeholder="e.g. An agent that answers employee questions about leave policy and can raise a ServiceNow request when they need HR support."
        disabled={loading}
      />
      <div style={{ marginTop: 12 }}>
        <button onClick={handleSubmit} disabled={loading}>
          {loading ? "Generating…" : "Next"}
        </button>
      </div>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </div>
  );
}
