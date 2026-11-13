import { useEffect, useState, FormEvent } from "react";
import { useMsal } from "@azure/msal-react";
import {
  AdminAgentTemplate,
  deleteAgentTemplate,
  listAgentTemplatesAdmin,
  registerAgentTemplate,
} from "../api";

// Mirrors catalog_mvp.py — the backend re-validates all of these
// independently, this just keeps the form from offering a value the
// server will reject anyway.
const DEPARTMENTS = ["HR", "Finance", "DevSecOps", "IT Support", "Admin", "Sales"];
const AGENT_TYPES = ["Knowledge Assistant", "Analyst", "Process Agent", "Action Agent", "Monitoring Agent"];
const PATTERNS = ["knowledge_only", "knowledge_action", "process", "monitoring"];
const MODEL_POLICIES = ["approved-general-enterprise", "approved-high-accuracy", "approved-fast-lowcost"];
const DATA_CLASSIFICATIONS = ["Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted"];

const EMPTY_FORM = {
  templateId: "",
  displayName: "",
  department: DEPARTMENTS[0],
  agentType: AGENT_TYPES[0],
  pattern: PATTERNS[0],
  purpose: "",
  modelPolicy: MODEL_POLICIES[0],
  dataClassification: "Internal",
  humanApproval: true,
  externalSharing: false,
  icon: "",
  description: "",
};

export default function AdminAgentTemplates() {
  const { instance } = useMsal();

  const [templates, setTemplates] = useState<AdminAgentTemplate[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  function loadTemplates() {
    setListLoading(true);
    setListError(null);
    listAgentTemplatesAdmin(instance)
      .then((res) => {
        setTemplates(res.templates);
        setAccessDenied(false);
      })
      .catch((e) => {
        const message = e instanceof Error ? e.message : "Failed to load agent templates.";
        if (message.toLowerCase().includes("catalog-admin access")) setAccessDenied(true);
        else setListError(message);
      })
      .finally(() => setListLoading(false));
  }

  useEffect(loadTemplates, [instance]);

  function startEditing(t: AdminAgentTemplate) {
    setEditingId(t.id);
    setForm({
      templateId: t.id,
      displayName: t.displayName,
      department: t.department,
      agentType: t.agentType,
      pattern: t.pattern,
      purpose: t.purpose,
      modelPolicy: t.modelPolicy,
      dataClassification: t.dataClassification,
      humanApproval: t.humanApproval,
      externalSharing: t.externalSharing,
      icon: t.icon,
      description: t.description,
    });
    setShowForm(true);
    setSubmitError(null);
    setSubmitSuccess(null);
  }

  function handleAddOrCloseForm() {
    setShowForm((open) => !open);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setSubmitError(null);
    setSubmitSuccess(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const wasEditing = editingId !== null;
    setSubmitError(null);
    setSubmitSuccess(null);

    if (!form.templateId.trim() || !form.displayName.trim() || !form.purpose.trim()) {
      setSubmitError("Template ID, display name, and purpose are required.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await registerAgentTemplate(instance, {
        templateId: form.templateId.trim(),
        displayName: form.displayName.trim(),
        department: form.department,
        agentType: form.agentType,
        pattern: form.pattern,
        purpose: form.purpose.trim(),
        modelPolicy: form.modelPolicy,
        dataClassification: form.dataClassification,
        humanApproval: form.humanApproval,
        externalSharing: form.externalSharing,
        icon: form.icon.trim(),
        description: form.description.trim(),
      });
      setSubmitSuccess(`${wasEditing ? "Updated" : "Registered"} "${result.id}"`);
      setEditingId(null);
      setForm(EMPTY_FORM);
      loadTemplates();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteAgentTemplate(instance, id);
      loadTemplates();
    } catch (e) {
      setListError(e instanceof Error ? e.message : "Failed to delete template.");
    }
  }

  if (accessDenied) {
    return (
      <section className="page">
        <p className="eyebrow">CATALOG ADMIN</p>
        <h1 className="pageTitle">Agent templates</h1>
        <div className="notice errorNotice">
          You don't have catalog-admin access. Contact your platform administrator if you believe this is wrong.
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <p className="eyebrow">CATALOG ADMIN</p>
      <h1 className="pageTitle">Agent templates</h1>
      <p className="pageIntro">
        These are the ready-made solutions shown on the Start page. A template only pre-fills the same fields a
        user's own description would — knowledge sources, tools, and audience are still picked by the user from the
        live, department-scoped catalog on Configure.
      </p>

      <button className="btn primary" type="button" onClick={handleAddOrCloseForm} style={{ marginBottom: 18 }}>
        {showForm ? "Close form" : "+ Add agent template"}
      </button>

      {showForm && (
        <form className="card formCard" onSubmit={handleSubmit} style={{ marginBottom: 22 }}>
          <div className="sectionTitle">{editingId ? "Edit agent template" : "Register agent template"}</div>
          <div className="formGrid">
            <label className="field">
              <span className="label">Template ID</span>
              <input
                className="input"
                value={form.templateId}
                disabled={editingId !== null}
                onChange={(e) => setForm((f) => ({ ...f, templateId: e.target.value }))}
                placeholder="e.g. it-service-desk"
              />
              <span className="fieldHint">
                {editingId ? "Cannot be changed when editing." : "Stable internal key. Re-registering the same ID updates it in place."}
              </span>
            </label>
            <label className="field">
              <span className="label">Display name</span>
              <input className="input" value={form.displayName}
                onChange={(e) => setForm((f) => ({ ...f, displayName: e.target.value }))}
                placeholder="e.g. IT Service Desk" />
            </label>
            <label className="field">
              <span className="label">Department</span>
              <select className="select" value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}>
                {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="label">Agent type</span>
              <select className="select" value={form.agentType} onChange={(e) => setForm((f) => ({ ...f, agentType: e.target.value }))}>
                {AGENT_TYPES.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="label">Pattern</span>
              <select className="select" value={form.pattern} onChange={(e) => setForm((f) => ({ ...f, pattern: e.target.value }))}>
                {PATTERNS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="label">Model policy</span>
              <select className="select" value={form.modelPolicy} onChange={(e) => setForm((f) => ({ ...f, modelPolicy: e.target.value }))}>
                {MODEL_POLICIES.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="label">Data classification</span>
              <select className="select" value={form.dataClassification} onChange={(e) => setForm((f) => ({ ...f, dataClassification: e.target.value }))}>
                {DATA_CLASSIFICATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="label">Card icon (short text)</span>
              <input className="input" value={form.icon} maxLength={6}
                onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))} placeholder="e.g. IT" />
            </label>
            <label className="field full">
              <span className="label">Purpose</span>
              <textarea className="textarea" rows={3} value={form.purpose}
                onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))}
                placeholder="1-3 sentences — this becomes the agent's instructions base." />
            </label>
            <label className="field full">
              <span className="label">Card description (shown on Start)</span>
              <input className="input" value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="e.g. Resolve employee IT requests and incidents." />
            </label>
          </div>

          <div className="optionCard" style={{ marginTop: 18 }}>
            <div><strong>Human approval required</strong><p className="fieldHint">Keep a person in control before this agent's actions run.</p></div>
            <input className="toggleCheck" type="checkbox" checked={form.humanApproval}
              onChange={(e) => setForm((f) => ({ ...f, humanApproval: e.target.checked }))} aria-label="Human approval required" />
          </div>
          <div className="optionCard">
            <div><strong>External sharing allowed</strong><p className="fieldHint">Leave off unless this template clearly needs it.</p></div>
            <input className="toggleCheck" type="checkbox" checked={form.externalSharing}
              onChange={(e) => setForm((f) => ({ ...f, externalSharing: e.target.checked }))} aria-label="External sharing allowed" />
          </div>

          {submitError && <div className="notice errorNotice" style={{ marginTop: 16 }}>{submitError}</div>}
          {submitSuccess && <div className="notice" style={{ marginTop: 16 }}>{submitSuccess}</div>}

          <div className="pageActions">
            <span />
            <button className="btn primary" type="submit" disabled={submitting}>
              {submitting ? "Saving…" : editingId ? "Save changes" : "Register template"}
            </button>
          </div>
        </form>
      )}

      {listLoading && <div className="card" style={{ textAlign: "center", padding: 35 }}>Loading agent templates</div>}
      {listError && <div className="notice errorNotice">{listError}</div>}

      {!listLoading && !listError && templates.length === 0 && (
        <div className="emptyState">
          <strong>No agent templates registered yet</strong>
          <p>Use "Add agent template" above to register the first one.</p>
        </div>
      )}

      {!listLoading && templates.length > 0 && (
        <div className="card catalog">
          {templates.map((t) => (
            <div className="row" key={t.id}>
              <div className="rowMain">
                <b>{t.displayName}</b>
                <small>{t.id} · {t.agentType} · {t.pattern}</small>
              </div>
              <span className="pill">{t.department}</span>
              <span className="pill">{t.dataClassification}</span>
              <button className="btn" type="button" onClick={() => startEditing(t)}>Edit</button>
              <button className="btn" type="button" onClick={() => handleDelete(t.id)}>Delete</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
