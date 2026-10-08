import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { getCatalogForDepartment } from "../api";

export default function Knowledge() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    coreDraft,
    catalog,
    setCatalog,
    selectedKnowledgeIds,
    setSelectedKnowledgeIds,
  } = useBlueprint();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!coreDraft) return;

    // Preserve existing catalog caching behavior.
    if (catalog && catalog.department === coreDraft.department) return;

    setLoading(true);

    getCatalogForDepartment(instance, coreDraft.department)
      .then(setCatalog)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load catalog")
      )
      .finally(() => setLoading(false));
  }, [coreDraft, catalog, instance, setCatalog]);

  if (!coreDraft) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Knowledge</h2>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          Go back to Describe first.
        </p>

        <button
          className="btn primary"
          onClick={() => navigate("/describe")}
        >
          Back to Describe
        </button>
      </div>
    );
  }

  function toggle(id: string) {
    setSelectedKnowledgeIds(
      selectedKnowledgeIds.includes(id)
        ? selectedKnowledgeIds.filter((x) => x !== id)
        : [...selectedKnowledgeIds, id]
    );
  }

  const knowledgeSources = catalog?.knowledgeSources ?? [];
  const selectedSources = knowledgeSources.filter((source) =>
    selectedKnowledgeIds.includes(source.id)
  );

  function getSourceIcon(displayName: string) {
    const name = displayName.toLowerCase();

    if (name.includes("sharepoint")) return "SP";
    if (name.includes("storage") || name.includes("blob")) return "ST";
    if (name.includes("search")) return "AI";
    if (name.includes("sql")) return "DB";
    if (name.includes("fabric")) return "F";
    return "KN";
  }

  function getSourceType(displayName: string) {
    const name = displayName.toLowerCase();

    if (name.includes("sharepoint")) return "Document repository";
    if (name.includes("storage") || name.includes("blob"))
      return "Enterprise file storage";
    if (name.includes("search")) return "Search index";
    if (name.includes("sql")) return "Structured data";
    if (name.includes("fabric")) return "Data & analytics";
    return "Enterprise knowledge source";
  }

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 20,
          marginBottom: 24,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 750,
              color: "var(--brand)",
              textTransform: "uppercase",
              letterSpacing: ".08em",
              marginBottom: 7,
            }}
          >
            Agent configuration
          </div>

          <h2
            style={{
              margin: 0,
              fontSize: 25,
              letterSpacing: "-.02em",
            }}
          >
            Knowledge
          </h2>

          <p
            style={{
              margin: "8px 0 0",
              color: "var(--muted)",
              fontSize: 13,
              lineHeight: 1.55,
              maxWidth: 620,
            }}
          >
            Connect your agent to approved enterprise data and knowledge
            sources. Only sources available to your department are shown.
          </p>
        </div>

        {/* Selection count */}
        <div
          style={{
            minWidth: 125,
            padding: "12px 14px",
            background: "#fff",
            border: "1px solid var(--line)",
            borderRadius: 10,
            textAlign: "right",
            boxShadow: "var(--shadow)",
          }}
        >
          <div
            style={{
              fontSize: 9,
              color: "#98a2b3",
              textTransform: "uppercase",
              fontWeight: 750,
              letterSpacing: ".06em",
            }}
          >
            Selected
          </div>

          <div
            style={{
              fontSize: 20,
              fontWeight: 750,
              marginTop: 3,
            }}
          >
            {selectedKnowledgeIds.length}
          </div>

          <div
            style={{
              fontSize: 9,
              color: "#98a2b3",
              marginTop: 1,
            }}
          >
            knowledge sources
          </div>
        </div>
      </div>

      {/* Department scope */}
      <div
        className="notice"
        style={{
          marginTop: 0,
          marginBottom: 18,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 15,
        }}
      >
        <div>
          <strong style={{ fontSize: 11 }}>Department scope</strong>
          <div style={{ marginTop: 3 }}>
            Showing approved knowledge sources for{" "}
            <strong>{coreDraft.department}</strong>.
          </div>
        </div>

        <span
          style={{
            background: "#fff",
            border: "1px solid #dbe2ff",
            borderRadius: 99,
            padding: "5px 9px",
            fontSize: 9,
            fontWeight: 750,
            whiteSpace: "nowrap",
          }}
        >
          APPROVED CATALOG
        </span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="card" style={{ textAlign: "center", padding: 35 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              marginBottom: 5,
            }}
          >
            Loading knowledge catalog
          </div>

          <div
            style={{
              fontSize: 11,
              color: "var(--muted)",
            }}
          >
            Checking approved sources for {coreDraft.department}…
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          className="card"
          style={{
            borderColor: "#f0c7c5",
            background: "#fffafa",
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 750,
              color: "#c4322d",
            }}
          >
            Unable to load knowledge catalog
          </div>

          <div
            style={{
              fontSize: 11,
              color: "#8f3430",
              marginTop: 5,
            }}
          >
            {error}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && knowledgeSources.length === 0 && (
        <div
          className="card"
          style={{
            textAlign: "center",
            padding: "45px 25px",
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              margin: "0 auto 14px",
              borderRadius: 12,
              background: "var(--brand2)",
              color: "var(--brand)",
              display: "grid",
              placeItems: "center",
              fontWeight: 800,
              fontSize: 12,
            }}
          >
            KN
          </div>

          <div
            style={{
              fontSize: 14,
              fontWeight: 750,
            }}
          >
            No approved knowledge sources
          </div>

          <p
            style={{
              fontSize: 11,
              color: "var(--muted)",
              maxWidth: 430,
              margin: "7px auto 0",
              lineHeight: 1.5,
            }}
          >
            There are currently no knowledge sources available for{" "}
            {coreDraft.department}.
          </p>
        </div>
      )}

      {/* Knowledge catalog */}
      {!loading && knowledgeSources.length > 0 && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 10,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 750,
                }}
              >
                Available knowledge
              </div>

              <div
                style={{
                  fontSize: 10,
                  color: "#98a2b3",
                  marginTop: 3,
                }}
              >
                Select the sources the agent is authorized to use.
              </div>
            </div>

            <span className="pill">
              {knowledgeSources.length}{" "}
              {knowledgeSources.length === 1 ? "source" : "sources"}
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 11,
            }}
          >
            {knowledgeSources.map((source) => {
              const selected = selectedKnowledgeIds.includes(source.id);

              return (
                <button
                  key={source.id}
                  type="button"
                  onClick={() => toggle(source.id)}
                  style={{
                    position: "relative",
                    textAlign: "left",
                    padding: 15,
                    borderRadius: 12,
                    border: selected
                      ? "1px solid var(--brand)"
                      : "1px solid var(--line)",
                    background: selected ? "#fafbff" : "#fff",
                    boxShadow: selected
                      ? "0 0 0 3px #eef2ff"
                      : "var(--shadow)",
                    cursor: "pointer",
                    transition: "all .15s ease",
                  }}
                >
                  {/* Selection indicator */}
                  <div
                    style={{
                      position: "absolute",
                      top: 14,
                      right: 14,
                      width: 20,
                      height: 20,
                      borderRadius: 6,
                      border: selected
                        ? "1px solid var(--brand)"
                        : "1px solid #cbd2dd",
                      background: selected
                        ? "var(--brand)"
                        : "#fff",
                      color: "#fff",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 11,
                      fontWeight: 800,
                    }}
                  >
                    {selected ? "✓" : ""}
                  </div>

                  {/* Source identity */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 11,
                      paddingRight: 28,
                    }}
                  >
                    <div
                      style={{
                        width: 39,
                        height: 39,
                        borderRadius: 10,
                        background: selected
                          ? "var(--brand)"
                          : "var(--brand2)",
                        color: selected ? "#fff" : "var(--brand)",
                        display: "grid",
                        placeItems: "center",
                        fontSize: 10,
                        fontWeight: 800,
                        flex: "none",
                      }}
                    >
                      {getSourceIcon(source.displayName)}
                    </div>

                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 750,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {source.displayName}
                      </div>

                      <div
                        style={{
                          fontSize: 9,
                          color: "#98a2b3",
                          marginTop: 3,
                        }}
                      >
                        {getSourceType(source.displayName)}
                      </div>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      marginTop: 14,
                    }}
                  >
                    <span className="pill">Approved</span>
                    <span className="pill">{coreDraft.department}</span>
                  </div>

                  {/* Source ID */}
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 10,
                      borderTop: "1px solid #f0f2f5",
                      fontSize: 9,
                      color: "#98a2b3",
                    }}
                  >
                    Source ID{" "}
                    <span
                      style={{
                        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                        color: "#667085",
                      }}
                    >
                      {source.id}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* Selected summary */}
      {selectedSources.length > 0 && (
        <div
          className="card"
          style={{
            marginTop: 18,
            padding: 15,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 10,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 750,
                }}
              >
                Selected knowledge
              </div>

              <div
                style={{
                  fontSize: 9,
                  color: "#98a2b3",
                  marginTop: 3,
                }}
              >
                These sources will be included in the agent blueprint.
              </div>
            </div>

            <span className="pill">
              {selectedSources.length} selected
            </span>
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 7,
            }}
          >
            {selectedSources.map((source) => (
              <div
                key={source.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "7px 9px",
                  border: "1px solid #dce2f5",
                  borderRadius: 8,
                  background: "#fafbff",
                }}
              >
                <span
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    background: "var(--brand2)",
                    color: "var(--brand)",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 8,
                    fontWeight: 800,
                  }}
                >
                  {getSourceIcon(source.displayName)}
                </span>

                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 650,
                  }}
                >
                  {source.displayName}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Navigation */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 25,
          paddingTop: 18,
          borderTop: "1px solid var(--line)",
        }}
      >
        <button
          className="btn"
          onClick={() => navigate("/context")}
        >
          ← Back
        </button>

        <button
          className="btn primary"
          onClick={() => navigate("/tools")}
        >
          Next: Actions →
        </button>
      </div>
    </div>
  );
}