import { useEffect, useState, FormEvent } from "react";
import { useMsal } from "@azure/msal-react";
import {
  AdminKnowledgeSource,
  AuditFinding,
  RegisterKnowledgeSourceResponse,
  auditKnowledgeSources,
  listKnowledgeSourcesAdmin,
  registerKnowledgeSource,
} from "../api";

// Mirrors catalog_mvp.py's DEPARTMENTS / Context.tsx's DATA_CLASSIFICATIONS.
// The backend re-validates both independently — this is just so the form
// doesn't let someone type a value the server will reject anyway.
const DEPARTMENTS = ["HR", "Finance", "DevSecOps", "IT Support", "Admin", "Sales"];
const DATA_CLASSIFICATIONS = ["Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted"];

const EMPTY_FORM = {
  sourceId: "",
  displayName: "",
  departments: [] as string[],
  dataClassification: "Internal",
  searchServiceEndpoint: "",
  knowledgeBaseName: "",
  agentFactoryReady: true,
};

const ISSUE_LABELS: Record<string, string> = {
  shared_connection: "Shared connection",
  target_mismatch: "Connection target mismatch",
  connection_missing: "Connection missing",
  connection_unreadable: "Connection unreadable",
  incomplete_entry: "Incomplete entry",
};

function AuditFindingRow({ finding }: { finding: AuditFinding }) {
  return (
    <div className="checkResult">
      <span className="checkStatus fail">!</span>
      <div>
        <strong>{finding.sourceId}</strong>
        <p>
          {ISSUE_LABELS[finding.issue] ?? finding.issue}
          {finding.connectionName ? ` — connection "${finding.connectionName}"` : ""}
          {finding.detail ? `: ${finding.detail}` : ""}
        </p>
      </div>
    </div>
  );
}

export default function AdminKnowledgeSources() {
  const { instance } = useMsal();

  const [sources, setSources] = useState<AdminKnowledgeSource[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [submitSuccessAction, setSubmitSuccessAction] = useState<
    "registered" | "updated" | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<RegisterKnowledgeSourceResponse | null>(null);

  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditResult, setAuditResult] = useState<{ findings: AuditFinding[]; clean: boolean } | null>(null);

  function loadSources() {
    setListLoading(true);
    setListError(null);
    listKnowledgeSourcesAdmin(instance)
      .then((res) => {
        setSources(res.knowledgeSources);
        setAccessDenied(false);
      })
      .catch((e) => {
        const message = e instanceof Error ? e.message : "Failed to load knowledge sources.";
        if (message.toLowerCase().includes("catalog-admin access")) {
          setAccessDenied(true);
        } else {
          setListError(message);
        }
      })
      .finally(() => setListLoading(false));
  }

  useEffect(loadSources, [instance]);

  function startEditing(source: AdminKnowledgeSource) {
    setEditingSourceId(source.sourceId);

    setForm({
      sourceId: source.sourceId,
      displayName: source.displayName,
      departments: [...(source.departments ?? [])],
      dataClassification: source.dataClassification || "Internal",
      searchServiceEndpoint: source.searchServiceEndpoint ?? "",
      knowledgeBaseName: source.knowledgeBaseName ?? "",
      agentFactoryReady: source.agentFactoryReady,
    });

    setShowForm(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    setSubmitSuccessAction(null);
  }

  function handleAddOrCloseForm() {
    setShowForm((currentlyOpen) => !currentlyOpen);
    setEditingSourceId(null);
    setForm(EMPTY_FORM);
    setSubmitError(null);
    setSubmitSuccess(null);
    setSubmitSuccessAction(null);
  }

  function toggleDepartment(dept: string) {
    setForm((f) => ({
      ...f,
      departments: f.departments.includes(dept)
        ? f.departments.filter((d) => d !== dept)
        : [...f.departments, dept],
    }));
  }

  async function handleSubmit(e: FormEvent) {
    const wasEditing = editingSourceId !== null;
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);
    setSubmitSuccessAction(null);

    if (!form.sourceId.trim() || !form.displayName.trim()) {
      setSubmitError("Source ID and display name are required.");
      return;
    }
    if (form.departments.length === 0) {
      setSubmitError("Select at least one department.");
      return;
    }
    if (!form.searchServiceEndpoint.trim() || !form.knowledgeBaseName.trim()) {
      setSubmitError("Search service endpoint and knowledge base name are required.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await registerKnowledgeSource(instance, {
        sourceId: form.sourceId.trim(),
        displayName: form.displayName.trim(),
        departments: form.departments,
        dataClassification: form.dataClassification,
        searchServiceEndpoint: form.searchServiceEndpoint.trim(),
        knowledgeBaseName: form.knowledgeBaseName.trim(),
        agentFactoryReady: form.agentFactoryReady,
      });
      setSubmitSuccess(result);
      setSubmitSuccessAction(wasEditing ? "updated" : "registered");
      setEditingSourceId(null);
      setForm(EMPTY_FORM);
      loadSources();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAudit() {
    setAuditLoading(true);
    setAuditError(null);
    setAuditResult(null);
    try {
      const result = await auditKnowledgeSources(instance);
      setAuditResult(result);
    } catch (e) {
      setAuditError(e instanceof Error ? e.message : "Consistency check failed.");
    } finally {
      setAuditLoading(false);
    }
  }

  if (accessDenied) {
    return (
      <section className="page">
        <p className="eyebrow">CATALOG ADMIN</p>
        <h1 className="pageTitle">Knowledge sources</h1>
        <div className="notice errorNotice">
          You don't have catalog-admin access. Contact your platform administrator if you believe this is wrong.
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <p className="eyebrow">CATALOG ADMIN</p>
      <h1 className="pageTitle">Knowledge sources</h1>
      <p className="pageIntro">
        Register the knowledge bases agents are allowed to use, and which departments can see each one.
        Registering provisions the matching Foundry connection automatically — there's no field for it
        here, because it can no longer be set by hand.
      </p>

      <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        <button className="btn primary" onClick={handleAddOrCloseForm} type="button">
          {showForm ? "Close form" : "+ Add knowledge source"}
        </button>
        <button className="btn" onClick={handleAudit} disabled={auditLoading}>
          {auditLoading ? "Checking…" : "Run consistency check"}
        </button>
      </div>

      {showForm && (
        <form className="card formCard" onSubmit={handleSubmit} style={{ marginBottom: 22 }}>
          <div className="sectionTitle">
            {editingSourceId ? "Edit knowledge source" : "Register knowledge source"}
            </div>
          <div className="formGrid">
            <label className="field">
              <span className="label">Source ID</span>
              <input
                className="input"
                value={form.sourceId}
                disabled={editingSourceId !== null}
                onChange={(e) => setForm((f) => ({ ...f, sourceId: e.target.value }))}
                placeholder="e.g. alpha-bank-policy"
              />
              <span className="fieldHint">{editingSourceId 
              ? "Source ID cannot be changed when editing."
              : "Stable internal key. Re-registering the same ID updates it in place."}</span>
            </label>
            <label className="field">
              <span className="label">Display name</span>
              <input
                className="input"
                value={form.displayName}
                onChange={(e) => setForm((f) => ({ ...f, displayName: e.target.value }))}
                placeholder="e.g. Alpha Bank Policy"
              />
            </label>
            <label className="field">
              <span className="label">Data classification</span>
              <select
                className="select"
                value={form.dataClassification}
                onChange={(e) => setForm((f) => ({ ...f, dataClassification: e.target.value }))}
              >
                {DATA_CLASSIFICATIONS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="label">Azure AI Search endpoint</span>
              <input
                className="input"
                value={form.searchServiceEndpoint}
                onChange={(e) => setForm((f) => ({ ...f, searchServiceEndpoint: e.target.value }))}
                placeholder="https://<service>.search.windows.net"
              />
            </label>
            <label className="field">
              <span className="label">Knowledge base name</span>
              <input
                className="input"
                value={form.knowledgeBaseName}
                onChange={(e) => setForm((f) => ({ ...f, knowledgeBaseName: e.target.value }))}
                placeholder="e.g. knowledgebase_alphabank"
              />
            </label>
            <div className="field full">
              <span className="label">Departments</span>
              <div className="choiceGrid">
                {DEPARTMENTS.map((dept) => {
                  const selected = form.departments.includes(dept);
                  return (
                    <button
                      type="button"
                      key={dept}
                      className={`choiceCard ${selected ? "selected" : ""}`}
                      onClick={() => toggleDepartment(dept)}
                    >
                      <strong>{dept}</strong>
                      {selected && <span className="selectedMark">Selected</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="optionCard" style={{ marginTop: 18 }}>
            <div>
              <strong>Visible to users</strong>
              <p className="fieldHint">Off keeps it registered but hidden from the Knowledge page (agentFactoryReady = false).</p>
            </div>
            <input
              className="toggleCheck"
              type="checkbox"
              checked={form.agentFactoryReady}
              onChange={(e) => setForm((f) => ({ ...f, agentFactoryReady: e.target.checked }))}
              aria-label="Visible to users"
            />
          </div>

          {submitError && <div className="notice errorNotice" style={{ marginTop: 16 }}>{submitError}</div>}
          {submitSuccess && (
            <div className="notice" style={{ marginTop: 16 }}>
              <strong> {submitSuccessAction === "updated" ? "Updated" : "Registered"} "{submitSuccess.sourceId}"</strong>
              <p>Connection: {submitSuccess.connectionName}</p>
              <p>MCP target: {submitSuccess.mcpTarget}</p>
            </div>
          )}

          <div className="pageActions">
            <span />
            <button className="btn primary" type="submit" disabled={submitting}>
              {submitting ? editingSourceId ? "Saving…" : "Registering…" : editingSourceId ? "Save changes" : "Register knowledge source"}
            </button>
          </div>
        </form>
      )}

      {auditError && <div className="notice errorNotice" style={{ marginBottom: 18 }}>{auditError}</div>}
      {auditResult && auditResult.clean && (
        <div className="notice" style={{ marginBottom: 18 }}>
          Clean — every knowledge source has its own connection, and every connection's live target matches what its registry entry expects.
        </div>
      )}
      {auditResult && !auditResult.clean && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="sectionTitle">Consistency check found {auditResult.findings.length} issue(s)</div>
          <div className="checkList">
            {auditResult.findings.map((f, i) => <AuditFindingRow key={`${f.sourceId}-${i}`} finding={f} />)}
          </div>
        </div>
      )}

      {listLoading && (
        <div className="card" style={{ textAlign: "center", padding: 35 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Loading knowledge sources</div>
        </div>
      )}

      {listError && <div className="notice errorNotice">{listError}</div>}

      {!listLoading && !listError && sources.length === 0 && (
        <div className="emptyState">
          <strong>No knowledge sources registered yet</strong>
          <p>Use "Add knowledge source" above to register the first one.</p>
        </div>
      )}

      {!listLoading && sources.length > 0 && (
        <div className="card catalog">
          {sources.map((s) => (
            <div className="row" key={s.sourceId}>
              <div className="rowMain">
                <b>{s.displayName}</b>
                <small>
                  {s.sourceId} · {s.knowledgeBaseName ?? "—"} · connection: {s.connectionName ?? "—"}
                </small>
              </div>
              <span className="pill">{s.departments.join(", ") || "No departments"}</span>
              <span className="pill">{s.dataClassification}</span>
              <span className={`pill ${s.agentFactoryReady ? "green" : "amber"}`}>
                {s.agentFactoryReady ? "Visible" : "Hidden"}
              </span>
              <button
              className="btn"
              type="button"
              onClick={() => startEditing(s)}
              >
                Edit
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
