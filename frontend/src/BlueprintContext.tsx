import { createContext, useContext, useState, ReactNode } from "react";
import { CoreBlueprintDraft, CatalogResponse, CompileResponse, CreatedAgent } from "./api";

export interface BehaviorPreferences {
  instructions: string;
  responseStyle: "Concise" | "Balanced" | "Detailed";
  citeSources: boolean;
  askClarifyingQuestions: boolean;
  escalateUncertainty: boolean;
}

// Instructions start empty and get set to the Describe page's generated
// `purpose` text the moment a draft is created (see Describe.tsx) — that's
// the "AI-generated instructions pre-fill the box" behavior. From then on
// it's just a normal field: whatever's in it (untouched or edited) is what
// gets sent, combined with the reliability-rule toggles below and the
// governance lines the backend always appends (api/blueprint/instructions.py).
export const defaultBehavior: BehaviorPreferences = {
  instructions: "",
  responseStyle: "Balanced",
  citeSources: true,
  askClarifyingQuestions: true,
  escalateUncertainty: true,
};

interface BlueprintState {
  description: string;
  setDescription: (v: string) => void;
  coreDraft: CoreBlueprintDraft | null;
  setCoreDraft: (v: CoreBlueprintDraft | null) => void;
  catalog: CatalogResponse | null;
  setCatalog: (v: CatalogResponse | null) => void;
  selectedKnowledgeIds: string[];
  setSelectedKnowledgeIds: (v: string[]) => void;
  selectedToolIds: string[];
  setSelectedToolIds: (v: string[]) => void;
  selectedAudienceIds: string[];
  setSelectedAudienceIds: (v: string[]) => void;
  behavior: BehaviorPreferences;
  setBehavior: (v: BehaviorPreferences) => void;
  compileResult: CompileResponse | null;
  setCompileResult: (v: CompileResponse | null) => void;
  createdAgent: CreatedAgent | null;
  setCreatedAgent: (v: CreatedAgent | null) => void;
  agentCreated: boolean;
  setAgentCreated: (v: boolean) => void;
}

const BlueprintContext = createContext<BlueprintState | undefined>(undefined);

export function BlueprintProvider({ children }: { children: ReactNode }) {
  const [description, setDescription] = useState("");
  const [coreDraft, setCoreDraft] = useState<CoreBlueprintDraft | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<string[]>([]);
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);
  const [selectedAudienceIds, setSelectedAudienceIds] = useState<string[]>([]);
  const [behavior, setBehavior] = useState<BehaviorPreferences>(defaultBehavior);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [createdAgent, setCreatedAgent] = useState<CreatedAgent | null>(null);
  const [agentCreated, setAgentCreated] = useState(false);

  return (
    <BlueprintContext.Provider value={{
      description, setDescription, coreDraft, setCoreDraft, catalog, setCatalog,
      selectedKnowledgeIds, setSelectedKnowledgeIds, selectedToolIds, setSelectedToolIds,
      selectedAudienceIds, setSelectedAudienceIds, behavior, setBehavior,
      compileResult, setCompileResult, createdAgent, setCreatedAgent, agentCreated, setAgentCreated,
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
