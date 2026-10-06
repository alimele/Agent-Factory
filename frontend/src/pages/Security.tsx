import { useNavigate } from "react-router-dom";
import { useBlueprint } from "../BlueprintContext";

export default function Security() {
  const navigate = useNavigate();
  const { coreDraft, catalog, selectedAudienceIds, setSelectedAudienceIds } = useBlueprint();

  if (!coreDraft) {
    return (
      <div>
        <h2>Security</h2>
        <p>Go back to Describe first.</p>
        <button onClick={() => navigate("/describe")}>Back to Describe</button>
      </div>
    );
  }

  function toggle(id: string) {
    setSelectedAudienceIds(
      selectedAudienceIds.includes(id)
        ? selectedAudienceIds.filter((x) => x !== id)
        : [...selectedAudienceIds, id]
    );
  }

  return (
    <div>
      <h2>Security</h2>
      <p>Who should be able to use this agent?</p>

      {!catalog && <p>Visit Knowledge or Actions first to load the audience list.</p>}

      {catalog?.audiences.map((a) => (
        <div key={a.id}>
          <label>
            <input
              type="checkbox"
              checked={selectedAudienceIds.includes(a.id)}
              onChange={() => toggle(a.id)}
            />
            {a.id}
          </label>
        </div>
      ))}

      <div style={{ marginTop: 12 }}>
        <button onClick={() => navigate("/review")} disabled={selectedAudienceIds.length === 0}>
          Next: Review
        </button>
      </div>
    </div>
  );
}
