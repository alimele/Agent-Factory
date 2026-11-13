import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { AgentRecordDto, listAgents, runTestAgent } from "../api";

interface ChatMessage { role: "user" | "agent"; text: string }

export default function Playground() {
  const { instance } = useMsal();

  const [agents, setAgents] = useState<AgentRecordDto[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents(instance)
      .then((all) => all.filter((a) => a.status === "dev_created" || a.status === "published"))
      .then(setAgents)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load your agents"))
      .finally(() => setLoading(false));
  }, [instance]);

  const selected = agents.find((a) => a.id === selectedId);

  async function send() {
    if (!selected?.foundryAgentName || !selected.foundryAgentVersion || !prompt.trim() || busy) return;
    const userText = prompt.trim();
    setMessages((m) => [...m, { role: "user", text: userText }]);
    setPrompt("");
    setBusy(true);
    setError(null);
    try {
      const result = await runTestAgent(instance, {
        agentName: selected.foundryAgentName,
        agentVersion: selected.foundryAgentVersion,
        prompt: userText,
      });
      setMessages((m) => [...m, { role: "agent", text: result.outputText }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The agent could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <p className="eyebrow">PLAYGROUND</p>
      <h1 className="pageTitle">Talk to any of your agents</h1>
      <p className="pageIntro">Every development or published agent you own shows up here — not just the one you just built.</p>

      {loading && <div className="card" style={{ textAlign: "center", padding: 30 }}>Loading your testable agents…</div>}
      {error && <div className="notice errorNotice">{error}</div>}

      {!loading && agents.length === 0 && (
        <div className="emptyState">
          <strong>No testable agents yet</strong>
          <p>Launch an agent from Review &amp; Launch first — it'll show up here.</p>
        </div>
      )}

      {agents.length > 0 && (
        <>
          <select
            className="select"
            value={selectedId}
            onChange={(e) => { setSelectedId(e.target.value); setMessages([]); setError(null); }}
          >
            <option value="">Choose an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.coreDraft.name} ({a.coreDraft.department})</option>
            ))}
          </select>

          {selected && (
            <div className="card playgroundChat schematicCard">
              <div className="chatLog">
                {messages.length === 0 && <p className="mutedText">Send a message to start testing {selected.coreDraft.name}.</p>}
                {messages.map((m, i) => <div key={i} className={`chatBubble ${m.role}`}>{m.text}</div>)}
              </div>
              <div className="chatInputRow">
                <input
                  className="input"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") send(); }}
                  placeholder="Type a test message…"
                  disabled={busy}
                />
                <button className="btn primary" onClick={send} disabled={busy || !prompt.trim()}>
                  {busy ? "…" : "Send"}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
