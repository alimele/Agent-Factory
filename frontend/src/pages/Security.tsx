import { useNavigate } from "react-router-dom";
import { useBlueprint } from "../BlueprintContext";

export default function Security() {
  const navigate = useNavigate();
  const { coreDraft, catalog, selectedAudienceIds, setSelectedAudienceIds } = useBlueprint();
  if (!coreDraft) return <section className="page"><h1 className="pageTitle">Security and access</h1><div className="notice">Start on Describe to configure an agent.</div><button className="btn primary" onClick={() => navigate("/describe")}>Back to Describe</button></section>;

  const audiences = catalog?.audiences ?? [];
  function toggle(id: string) {
    setSelectedAudienceIds(selectedAudienceIds.includes(id) ? selectedAudienceIds.filter(x => x !== id) : [...selectedAudienceIds, id]);
  }
  return <section className="page">
    <p className="eyebrow">AGENT CONFIGURATION · STEP 6 OF 10</p>
    <h1 className="pageTitle">Secure access to your agent</h1>
    <p className="pageIntro">Choose the approved audience for <strong>{coreDraft.name}</strong>. Only select groups that should be allowed to use this agent.</p>
    <div className="securitySummary"><div className="securityIcon">♙</div><div><strong>Access scope</strong><p>Department: {coreDraft.department || "Not specified"}</p></div><span className="pill">{selectedAudienceIds.length} selected</span></div>
    <div className="sectionHeading"><div><h2 className="sectionTitle">Authorized audiences</h2><p className="pageIntro compact">Select one or more groups from the enterprise catalog.</p></div></div>
    {!catalog && <div className="notice warn">The audience catalog has not loaded yet. Visit Knowledge or Tools to load the department catalog, then return here.</div>}
    {catalog && audiences.length === 0 && <div className="emptyState"><strong>No audiences are configured</strong><p>Ask your administrator to add approved audiences to the catalog for this department.</p></div>}
    {audiences.length > 0 && <div className="catalog securityCatalog">{audiences.map(a => { const selected = selectedAudienceIds.includes(a.id); return <label key={a.id} className={`audienceRow ${selected ? "isSelected" : ""}`}><span className={`check ${selected ? "on" : ""}`}>{selected ? "✓" : ""}</span><span className="audienceCopy"><strong>{a.id}</strong><small>Enterprise access group</small></span><input type="checkbox" className="visuallyHidden" checked={selected} onChange={() => toggle(a.id)} aria-label={`Allow ${a.id}`} /></label>; })}</div>}
    <div className="notice">The selected audience IDs are passed to blueprint compilation. Actual identity-group enforcement must be configured in the deployed agent and its hosting environment.</div>
    <div className="pageActions"><button className="btn" onClick={() => navigate("/behavior")}>Back</button><button className="btn primary" onClick={() => navigate("/review")} disabled={selectedAudienceIds.length === 0}>Review blueprint <span aria-hidden="true">→</span></button></div>
  </section>;
}
