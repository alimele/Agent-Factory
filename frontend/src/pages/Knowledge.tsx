import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { getCatalogForDepartment } from "../api";

export default function Knowledge() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { coreDraft, catalog, setCatalog, selectedKnowledgeIds, setSelectedKnowledgeIds } = useBlueprint();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!coreDraft) return;
    // Only re-fetch if we don't already have the catalog for this department
    // (e.g. user went Describe -> Context -> Knowledge -> back -> forward).
    if (catalog && catalog.department === coreDraft.department) return;

    setLoading(true);
    getCatalogForDepartment(instance, coreDraft.department)
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load catalog"))
      .finally(() => setLoading(false));
  }, [coreDraft, catalog, instance, setCatalog]);

  if (!coreDraft) {
    return (
      <div>
        <h2>Knowledge</h2>
        <p>Go back to Describe first.</p>
        <button onClick={() => navigate("/describe")}>Back to Describe</button>
      </div>
    );
  }

  function toggle(id: string) {
    setSelectedKnowledgeIds(
      selectedKnowledgeIds.includes(id)
        ? selectedKnowledgeIds.filter((x) => x !== id)
        : [...selectedKnowledgeIds, id]
    );
  }

  return (
    <div>
      <h2>Knowledge</h2>
      <p>Pick the sources this agent should be grounded in — leave all unchecked if it doesn't need any.</p>

      {loading && <p>Loading approved knowledge sources for {coreDraft.department}…</p>}
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {catalog?.knowledgeSources.length === 0 && !loading && (
        <p>No approved knowledge sources for {coreDraft.department} yet.</p>
      )}

      {catalog?.knowledgeSources.map((k) => (
        <div key={k.id}>
          <label>
            <input
              type="checkbox"
              checked={selectedKnowledgeIds.includes(k.id)}
              onChange={() => toggle(k.id)}
            />
            {k.displayName}
          </label>
        </div>
      ))}

      <div style={{ marginTop: 12 }}>
        <button onClick={() => navigate("/tools")}>Next: Actions</button>
      </div>
    </div>
  );
}
