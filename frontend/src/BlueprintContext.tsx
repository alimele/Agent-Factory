import { createContext, useContext, useState, ReactNode } from "react";
import { CoreBlueprintDraft, CatalogResponse, CompileResponse, CreatedAgent, AgentRecordDto, ToolSelection, ToolOperationsResponse } from "./api";

export interface BehaviorPreferences {
  instructions: string;
  responseStyle: "Concise" | "Balanced" | "Detailed";
  citeSources: boolean;
  askClarifyingQuestions: boolean;
  escalateUncertainty: boolean;
}

// Instructions start empty and get set to the generated `purpose` text the
// moment a draft is created (Start.tsx, from either a template or a typed
// description) — that's the "AI-generated instructions pre-fill the box"
// behavior. From then on it's just a normal field: whatever's in it
// (untouched or edited) is what gets sent, combined with the
// reliability-rule toggles below and the governance lines the backend
// always appends (api/blueprint/instructions.py).
export const defaultBehavior: BehaviorPreferences = {
  instructions: "",
  responseStyle: "Balanced",
  citeSources: true,
  askClarifyingQuestions: true,
  escalateUncertainty: true,
};

interface BlueprintState {
  // Identity of the agent record this session is editing — null until
  // Start.tsx has saved the first draft. This is what lets Configure /
  // Review & Launch keep autosaving onto the *same* persisted record
  // instead of creating a new one every time, and what My Agents passes
  // back in via loadRecord() to resume one after a reload.
  agentId: string | null;
  setAgentId: (v: string | null) => void;
  templateId: string | null;
  setTemplateId: (v: string | null) => void;

  description: string;
  setDescription: (v: string) => void;
  coreDraft: CoreBlueprintDraft | null;
  setCoreDraft: (v: CoreBlueprintDraft | null) => void;
  catalog: CatalogResponse | null;
  setCatalog: (v: CatalogResponse | null) => void;
  selectedKnowledgeIds: string[];
  setSelectedKnowledgeIds: (v: string[]) => void;
  // Per-server, per-operation tool selections — what's actually sent as
  // the blueprint's `tools` and what the agent receives. A server with an
  // empty `operations` array is a server the user has opened/connected but
  // not yet picked any operation on, kept in state only while the Tools
  // tab accordion is building it up — setToolOperations prunes it to [] on
  // submit so it never reaches compile/create-test-agent with 0 operations.
  toolSelections: ToolSelection[];
  setToolSelections: (v: ToolSelection[]) => void;
  /** Replace the operations selected for one server, adding or removing it from toolSelections as needed. */
  setToolOperations: (serverId: string, operations: string[]) => void;
  // Session cache of each server's discovery result (operations list, or
  // needs_connection/discovery_failed status), so switching Configure tabs
  // doesn't re-trigger a discovery call for a server already opened once.
  toolDiscovery: Record<string, ToolOperationsResponse>;
  setToolDiscovery: (v: Record<string, ToolOperationsResponse>) => void;
  selectedAudienceIds: string[];
  setSelectedAudienceIds: (v: string[]) => void;
  toolConnections: Record<string, string>; // serverId -> connectionId
  setToolConnections: (v: Record<string, string>) => void;
  behavior: BehaviorPreferences;
  setBehavior: (v: BehaviorPreferences) => void;
  compileResult: CompileResponse | null;
  setCompileResult: (v: CompileResponse | null) => void;
  createdAgent: CreatedAgent | null;
  setCreatedAgent: (v: CreatedAgent | null) => void;
  agentCreated: boolean;
  setAgentCreated: (v: boolean) => void;

  /** Hydrate the whole working state from a persisted record (My Agents → open). */
  loadRecord: (record: AgentRecordDto) => void;
  /** Clear everything so Start.tsx begins a genuinely new agent. */
  resetForNewAgent: () => void;
}

const BlueprintContext = createContext<BlueprintState | undefined>(undefined);

export function BlueprintProvider({ children }: { children: ReactNode }) {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [coreDraft, setCoreDraft] = useState<CoreBlueprintDraft | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<string[]>([]);
  const [toolSelections, setToolSelections] = useState<ToolSelection[]>([]);
  const [toolDiscovery, setToolDiscovery] = useState<Record<string, ToolOperationsResponse>>({});
  const [selectedAudienceIds, setSelectedAudienceIds] = useState<string[]>([]);
  const [toolConnections, setToolConnections] = useState<Record<string, string>>({});

  function setToolOperations(serverId: string, operations: string[]) {
    setToolSelections((prev) => {
      const without = prev.filter((s) => s.serverId !== serverId);
      return operations.length > 0 ? [...without, { serverId, operations }] : without;
    });
  }
  const [behavior, setBehavior] = useState<BehaviorPreferences>(defaultBehavior);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [createdAgent, setCreatedAgent] = useState<CreatedAgent | null>(null);
  const [agentCreated, setAgentCreated] = useState(false);

  function loadRecord(record: AgentRecordDto) {
    setAgentId(record.id);
    setTemplateId(record.templateId ?? null);
    setCoreDraft(record.coreDraft);
    setCatalog(null); // force a fresh department catalog fetch on Configure
    setSelectedKnowledgeIds(record.knowledgeSourceIds);
    setToolSelections(record.toolSelections ?? []);
    setToolDiscovery({});
    setSelectedAudienceIds(record.audienceIds);
    // Per-user tool connections aren't reusable across sessions/devices by
    // this backend by design (see tool_connections.py) — the user
    // reconnects on resume, which also re-runs discovery for that server.
    setToolConnections({});
    setBehavior({ ...defaultBehavior, ...(record.behavior as Partial<BehaviorPreferences>) });
    setCompileResult(
      record.blueprint && record.foundryPayload
        ? { blueprint: record.blueprint, foundryPayload: record.foundryPayload }
        : null
    );
    if (record.foundryAgentName && record.foundryAgentVersion) {
      setCreatedAgent({
        name: record.foundryAgentName,
        id: null,
        version: record.foundryAgentVersion,
        model: "",
        status: "created",
        environment: "development",
      });
      setAgentCreated(true);
    } else {
      setCreatedAgent(null);
      setAgentCreated(false);
    }
  }

  function resetForNewAgent() {
    setAgentId(null);
    setTemplateId(null);
    setDescription("");
    setCoreDraft(null);
    setCatalog(null);
    setSelectedKnowledgeIds([]);
    setToolSelections([]);
    setToolDiscovery({});
    setSelectedAudienceIds([]);
    setToolConnections({});
    setBehavior(defaultBehavior);
    setCompileResult(null);
    setCreatedAgent(null);
    setAgentCreated(false);
  }

  return (
    <BlueprintContext.Provider value={{
      agentId, setAgentId, templateId, setTemplateId,
      description, setDescription, coreDraft, setCoreDraft, catalog, setCatalog,
      selectedKnowledgeIds, setSelectedKnowledgeIds,
      toolSelections, setToolSelections, setToolOperations, toolDiscovery, setToolDiscovery,
      selectedAudienceIds, setSelectedAudienceIds, toolConnections, setToolConnections, behavior, setBehavior,
      compileResult, setCompileResult, createdAgent, setCreatedAgent, agentCreated, setAgentCreated,
      loadRecord, resetForNewAgent,
    }}>
      {children}
    </BlueprintContext.Provider>
  );
}

export function useBlueprint(): BlueprintState {
  const ctx = useContext(BlueprintContext);
  if (!ctx) throw new Error("useBlueprint must be used inside <BlueprintProvider>");
  return ctx;
}
