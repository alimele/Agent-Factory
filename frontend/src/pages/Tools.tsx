import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { useBlueprint } from "../BlueprintContext";
import { getCatalogForDepartment } from "../api";

export default function Tools() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const {
    coreDraft,
    catalog,
    setCatalog,
    selectedToolIds,
    setSelectedToolIds,
  } = useBlueprint();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!coreDraft) return;
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
        <h2 style={{ marginTop: 0 }}>Actions</h2>
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
    setSelectedToolIds(
      selectedToolIds.includes(id)
        ? selectedToolIds.filter((x) => x !== id)
        : [...selectedToolIds, id]
    );
  }

  const tools = catalog?.tools ?? [];

  const selectedTools = tools.filter((tool) =>
    selectedToolIds.includes(tool.id)
  );

  function getRiskClass(risk?: string) {
    if (!risk) return "";
    const value = risk.toLowerCase();

    if (value === "high" || value === "critical") return "amber";
    if (value === "low") return "green";

    return "";
  }

  function getToolIcon(displayName: string) {
    const name = displayName.toLowerCase();

    if (
      name.includes("search") ||
      name.includes("query")
    )
      return "Q";

    if (
      name.includes("database") ||
      name.includes("sql") ||
      name.includes("record")
    )
      return "DB";

    if (
      name.includes("ticket") ||
      name.includes("incident") ||
      name.includes("case")
    )
      return "TK";

    if (
      name.includes("email") ||
      name.includes("mail")
    )
      return "EM";

    if (
      name.includes("api") ||
      name.includes("http")
    )
      return "API";

    return "TO";
  }

  function getToolType(displayName: string) {
    const name = displayName.toLowerCase();

    if (name.includes("search") || name.includes("query"))
      return "Query & search";

    if (
      name.includes("database") ||
      name.includes("sql")
    )
      return "Database";

    if (
      name.includes("ticket") ||
      name.includes("incident") ||
      name.includes("case")
    )
      return "Service operation";

    if (
      name.includes("email") ||
      name.includes("mail")
    )
      return "Communication";

    if (
      name.includes("api") ||
      name.includes("http")
    )
      return "API integration";

    return "Enterprise action";
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
            Actions
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
            Choose the approved tools this agent is allowed to use.
            Actions are governed by your department's approved tool catalog.
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
            {selectedToolIds.length}
          </div>

          <div
            style={{
              fontSize: 9,
              color: "#98a2b3",
              marginTop: 1,
            }}
          >
            actions
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
            Showing approved actions for{" "}
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
        <div
          className="card"
          style={{
            textAlign: "center",
            padding: 35,
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              marginBottom: 5,
            }}
          >
            Loading action catalog
          </div>

          <div
            style={{
              fontSize: 11,
              color: "var(--muted)",
            }}
          >
            Checking approved tools for {coreDraft.department}…
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
            Unable to load action catalog
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
      {!loading && !error && tools.length === 0 && (
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
            TO
          </div>

          <div
            style={{
              fontSize: 14,
              fontWeight: 750,
            }}
          >
            No approved actions
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
            There are currently no approved tools available for{" "}
            {coreDraft.department}.
          </p>
        </div>
      )}

      {/* Catalog */}
      {!loading && tools.length > 0 && (
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
                Available actions
              </div>

              <div
                style={{
                  fontSize: 10,
                  color: "#98a2b3",
                  marginTop: 3,
                }}
              >
                Select only the capabilities this agent actually needs.
              </div>
            </div>

            <span className="pill">
              {tools.length}{" "}
              {tools.length === 1 ? "tool" : "tools"}
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
            {tools.map((tool) => {
              const selected = selectedToolIds.includes(tool.id);
              const riskClass = getRiskClass(tool.risk);

              return (
                <button
                  key={tool.id}
                  type="button"
                  onClick={() => toggle(tool.id)}
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
                  {/* Checkbox */}
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

                  {/* Tool identity */}
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
                        color: selected
                          ? "#fff"
                          : "var(--brand)",
                        display: "grid",
                        placeItems: "center",
                        fontSize: 9,
                        fontWeight: 800,
                        flex: "none",
                      }}
                    >
                      {getToolIcon(tool.displayName)}
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
                        {tool.displayName}
                      </div>

                      <div
                        style={{
                          fontSize: 9,
                          color: "#98a2b3",
                          marginTop: 3,
                        }}
                      >
                        {getToolType(tool.displayName)}
                      </div>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      flexWrap: "wrap",
                      marginTop: 14,
                    }}
                  >
                    <span className="pill">Approved</span>

                    {tool.risk && (
                      <span className={`pill ${riskClass}`}>
                        {tool.risk} risk
                      </span>
                    )}

                    <span className="pill">
                      {coreDraft.department}
                    </span>
                  </div>

                  {/* Tool ID */}
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 10,
                      borderTop: "1px solid #f0f2f5",
                      fontSize: 9,
                      color: "#98a2b3",
                    }}
                  >
                    Tool ID{" "}
                    <span
                      style={{
                        fontFamily:
                          "ui-monospace, SFMono-Regular, Menlo, monospace",
                        color: "#667085",
                      }}
                    >
                      {tool.id}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* Selected summary */}
      {selectedTools.length > 0 && (
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
                Selected actions
              </div>

              <div
                style={{
                  fontSize: 9,
                  color: "#98a2b3",
                  marginTop: 3,
                }}
              >
                These capabilities will be included in the agent blueprint.
              </div>
            </div>

            <span className="pill">
              {selectedTools.length} selected
            </span>
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 7,
            }}
          >
            {selectedTools.map((tool) => (
              <div
                key={tool.id}
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
                  {getToolIcon(tool.displayName)}
                </span>

                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 650,
                  }}
                >
                  {tool.displayName}
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
          onClick={() => navigate("/knowledge")}
        >
          ← Back
        </button>

        <button
          className="btn primary"
          onClick={() => navigate("/security")}
        >
          Next: Security &amp; Audience →
        </button>
      </div>
    </div>
  );
}