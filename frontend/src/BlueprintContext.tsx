import { createContext, useContext, useState, ReactNode } from "react";
import { CoreBlueprintDraft, CatalogResponse, CompileResponse } from "./api";

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

  compileResult: CompileResponse | null;
  setCompileResult: (v: CompileResponse | null) => void;
}

const BlueprintContext = createContext<BlueprintState | undefined>(undefined);

export function BlueprintProvider({ children }: { children: ReactNode }) {
  const [description, setDescription] = useState("");
  const [coreDraft, setCoreDraft] = useState<CoreBlueprintDraft | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<string[]>([]);
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);
  const [selectedAudienceIds, setSelectedAudienceIds] = useState<string[]>([]);
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);

  return (
    <BlueprintContext.Provider
      value={{
        description, setDescription,
        coreDraft, setCoreDraft,
        catalog, setCatalog,
        selectedKnowledgeIds, setSelectedKnowledgeIds,
        selectedToolIds, setSelectedToolIds,
        selectedAudienceIds, setSelectedAudienceIds,
        compileResult, setCompileResult,
      }}
    >
      {children}
    </BlueprintContext.Provider>
  );
}

export function useBlueprint(): BlueprintState {
  const ctx = useContext(BlueprintContext);
  if (!ctx) throw new Error("useBlueprint must be used inside <BlueprintProvider>");
  return ctx;
}
