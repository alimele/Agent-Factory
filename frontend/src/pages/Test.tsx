import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { runTestAgent } from "../api";

export default function Test() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const { createdAgent } = useBlueprint();
  const [prompt, setPrompt] = useState("Without calling any tools or performing actions, describe your purpose and operating rules.");
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRunTest() {
    if (!createdAgent || !prompt.trim()) return;
    setLoading(true); setError(null); setOutput(null);
    try {
      const result = await runTestAgent(instance, {
        agentName: createdAgent.name,
        agentVersion: createdAgent.version,
        prompt: prompt.trim(),
      });
      setOutput(result.outputText);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The Foundry test query failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!createdAgent) return (
    <section className="page">
      <p className="eyebrow">AGENT CONFIGURATION · STEP 8 OF 10</p>
      <h1 className="pageTitle">Test your agent</h1>
      <div className="notice">Create a development agent from Review before running a test prompt.</div>
      <button className="btn primary" onClick={() => navigate("/review")}>Back to Review</button>
    </section>
  );

  return (
    <section className="page">
      <p className="eyebrow">AGENT CONFIGURATION · STEP 8 OF 10</p>
      <h1 className="pageTitle">Test your Foundry agent</h1>
      <p className="pageIntro">Send a prompt to the development version created in Microsoft Foundry.</p>
      <div className="card">
        <h2 className="sectionTitle">Development agent</h2>
        <div className="summaryGrid">
          <div className="summaryCard"><span>Name</span><strong>{createdAgent.name}</strong></div>
          <div className="summaryCard"><span>Version</span><strong>{createdAgent.version}</strong></div>
          <div className="summaryCard"><span>Model deployment</span><strong>{createdAgent.model}</strong></div>
        </div>
      </div>
      <div className="notice warn">Important: this sends a real prompt to Foundry. If the agent has action tools, it may call connected APIs. Use only read-only or sandbox/test APIs until Phase 5 implements the human approval and publish workflow.</div>
      <div className="card">
        <label className="field"><span className="label">Test prompt</span><textarea className="textarea" rows={5} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Enter a test prompt..." /></label>
        <div className="pageActions"><button className="btn" onClick={() => navigate("/review")}>Back to Review</button><button className="btn primary" onClick={handleRunTest} disabled={loading || !prompt.trim()}>{loading ? "Running test…" : "Run test prompt"}</button></div>
      </div>
      {error && <div className="notice errorNotice">{error}</div>}
      {output !== null && <div className="reviewSection"><h2 className="sectionTitle">Agent response</h2><div className="card"><pre className="testOutput">{output}</pre></div></div>}
    </section>
  );
}

