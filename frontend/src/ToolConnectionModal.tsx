import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { getToolConnectionSchema, connectTool, ToolConnectionField } from "./api";

export default function ToolConnectionModal({
  toolId, toolName, onClose, onConnected,
}: {
  toolId: string; toolName: string;
  onClose: () => void;
  onConnected: (connectionId: string) => void;
}) {
  const { instance } = useMsal();
  const [fields, setFields] = useState<ToolConnectionField[] | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getToolConnectionSchema(instance, toolId)
      .then((res) => {
        setFields(res.fields);
        const defaults: Record<string, string> = {};
        res.fields.forEach((f) => { if (f.default !== undefined) defaults[f.key] = String(f.default); });
        setValues(defaults);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load connection requirements"));
  }, [toolId, instance]);

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const res = await connectTool(instance, toolId, values);
      onConnected(res.connectionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Connect {toolName}</h3>
        {!fields && !error && <p>Loading…</p>}
        {error && <div className="notice errorNotice">{error}</div>}
        {fields && fields.map((f) => (
          <label key={f.key} className="field">
            <span className="label">{f.label}{f.required !== false && " *"}</span>
            <input
              className="input"
              type={f.type === "secret" ? "password" : f.type === "number" ? "number" : "text"}
              value={values[f.key] ?? ""}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
            />
          </label>
        ))}
        <div className="pageActions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={submit} disabled={saving || !fields}>
            {saving ? "Connecting…" : "Connect"}
          </button>
        </div>
      </div>
    </div>
  );
}