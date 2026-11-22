import { useOfficeStore } from "../../store/officeStore";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";
import { DESK_LAYOUT, getStatusColor } from "../scene/officeLayout";

export function BottomRoster() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const selectedAgentId = useOfficeStore((s) => s.selectedAgentId);
  const selectAgent = useOfficeStore((s) => s.selectAgent);
  const lastError = useOfficeStore((s) => s.lastError);
  const clearError = useOfficeStore((s) => s.clearError);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;
  const agents = normalizeOfficeAgents(activeProject?.agents);
  const latestEvent =
    activeProject && activeProject.timeline.length > 0
      ? activeProject.timeline[activeProject.timeline.length - 1]
      : null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 12,
        left: 12,
        right: 12,
        zIndex: 20,
        display: "flex",
        flexDirection: "column",
        gap: 6,
        pointerEvents: "none",
      }}
    >
      {lastError && (
        <div
          className="glass-panel"
          style={{
            alignSelf: "center",
            pointerEvents: "auto",
            padding: "6px 14px",
            borderRadius: 999,
            borderColor: "#ef4444",
            color: "#fca5a5",
            fontSize: 12,
            display: "flex",
            gap: 10,
            alignItems: "center",
          }}
        >
          <span>{lastError}</span>
          <button
            type="button"
            onClick={clearError}
            style={{
              background: "transparent",
              border: "none",
              color: "#ffffff",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            ×
          </button>
        </div>
      )}

      <div
        className="glass-panel"
        style={{
          pointerEvents: "auto",
          borderRadius: 14,
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          overflowX: "auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {Object.values(agents).map((agent) => {
            const color = getStatusColor(agent.status);
            const active = selectedAgentId === agent.id;
            return (
              <button
                key={agent.id}
                type="button"
                onClick={() => selectAgent(agent.id, DESK_LAYOUT[agent.role].standPos)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderRadius: 9,
                  background: active ? "rgba(59,130,246,0.24)" : "rgba(15,23,42,0.75)",
                  border: active
                    ? "1px solid #60a5fa"
                    : "1px solid rgba(148,163,184,0.2)",
                  color: "#f1f5f9",
                  fontSize: 12,
                  whiteSpace: "nowrap",
                  cursor: "pointer",
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: color,
                  }}
                />
                <span>{agent.name}</span>
              </button>
            );
          })}
        </div>

        {latestEvent && (
          <div
            style={{
              fontSize: 11,
              color: "#94a3b8",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              maxWidth: 360,
            }}
          >
            <strong style={{ color: "#cbd5e1" }}>{latestEvent.actor}:</strong> {latestEvent.text}
          </div>
        )}
      </div>
    </div>
  );
}
