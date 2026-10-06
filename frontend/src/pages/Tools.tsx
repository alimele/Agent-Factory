import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { getCatalogForDepartment } from "../api";

export default function Tools() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { coreDraft, catalog, setCatalog, selectedToolIds, setSelectedToolIds } = useBlueprint();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!coreDraft) return;
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
        <h2>Actions</h2>
        <p>Go back to Describe first.</p>
        <button onClick={() => navigate("/describe")}>Back to Describe</button>
      </div>
    );
  }

  function toggle(id: string) {
    setSelectedToolIds(
      selectedToolIds.includes(id) ? selectedToolIds.filter((x) => x !== id) : [...selectedToolIds, id]
    );
  }

  return (
    <div>
      <h2>Actions</h2>
      <p>Pick the tools this agent may use — leave all unchecked if it only answers questions.</p>

      {loading && <p>Loading approved tools for {coreDraft.department}…</p>}
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {catalog?.tools.length === 0 && !loading && (
        <p>No approved tools for {coreDraft.department} yet.</p>
      )}

      {catalog?.tools.map((t) => (
        <div key={t.id}>
          <label>
            <input
              type="checkbox"
              checked={selectedToolIds.includes(t.id)}
              onChange={() => toggle(t.id)}
            />
            {t.displayName} {t.risk && <em>({t.risk} risk)</em>}
          </label>
        </div>
      ))}

      <div style={{ marginTop: 12 }}>
        <button onClick={() => navigate("/security")}>Next: Security &amp; Audience</button>
      </div>
    </div>
  );
}
