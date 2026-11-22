import { ExternalLink, Monitor, Smartphone, Tablet, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useOfficeStore } from "../../store/officeStore";

export function PreviewDrawer() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const show = useOfficeStore((s) => s.showPreviewDrawer);
  const setShow = useOfficeStore((s) => s.setShowPreviewDrawer);

  const [tab, setTab] = useState<"preview" | "tokens">("preview");
  const [viewport, setViewport] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [tokensData, setTokensData] = useState<Record<string, unknown> | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  useEffect(() => {
    if (!show || !activeProject?.tokens_json_url) return;
    fetch(activeProject.tokens_json_url)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setTokensData(d))
      .catch(() => setTokensData(null));
  }, [show, activeProject?.id, activeProject?.tokens_json_url]);

  if (!show || !activeProject) return null;

  const frameWidth =
    viewport === "desktop" ? "100%" : viewport === "tablet" ? "768px" : "375px";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 45,
        background: "rgba(2,6,23,0.7)",
        backdropFilter: "blur(5px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 18,
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: "100%",
          maxWidth: 1200,
          height: "90vh",
          borderRadius: 16,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "12px 16px",
            borderBottom: "1px solid rgba(148,163,184,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              onClick={() => setTab("preview")}
              style={tabBtnStyle(tab === "preview")}
            >
              Live Web Preview
            </button>
            <button
              type="button"
              onClick={() => setTab("tokens")}
              style={tabBtnStyle(tab === "tokens")}
            >
              Figma tokens.json (Offline)
            </button>
          </div>

          {tab === "preview" && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <button
                type="button"
                onClick={() => setViewport("desktop")}
                style={tabBtnStyle(viewport === "desktop")}
              >
                <Monitor size={14} /> Desktop
              </button>
              <button
                type="button"
                onClick={() => setViewport("tablet")}
                style={tabBtnStyle(viewport === "tablet")}
              >
                <Tablet size={14} /> 768px
              </button>
              <button
                type="button"
                onClick={() => setViewport("mobile")}
                style={tabBtnStyle(viewport === "mobile")}
              >
                <Smartphone size={14} /> 375px
              </button>
              {activeProject.preview_url && (
                <a
                  href={activeProject.preview_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: "#93c5fd",
                    fontSize: 12,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    marginLeft: 8,
                    textDecoration: "none",
                  }}
                >
                  Mở tab mới <ExternalLink size={13} />
                </a>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => setShow(false)}
            style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
          >
            <X size={18} />
          </button>
        </div>

        <div
          style={{
            flex: 1,
            overflow: "auto",
            background: "#020617",
            display: "flex",
            justifyContent: "center",
            padding: tab === "preview" ? 14 : 18,
          }}
        >
          {tab === "preview" ? (
            activeProject.preview_url ? (
              <iframe
                key={`${activeProject.id}-${activeProject.qa_round}`}
                src={activeProject.preview_url}
                title="Preview Web"
                style={{
                  width: frameWidth,
                  maxWidth: "100%",
                  height: "100%",
                  border: "1px solid rgba(148,163,184,0.3)",
                  borderRadius: 10,
                  background: "#ffffff",
                }}
              />
            ) : (
              <div style={{ color: "#94a3b8", marginTop: 40 }}>Chưa có URL preview.</div>
            )
          ) : (
            <pre
              style={{
                width: "100%",
                margin: 0,
                padding: 14,
                borderRadius: 10,
                background: "#0f172a",
                color: "#a7f3d0",
                fontSize: 12,
                overflow: "auto",
              }}
            >
              {JSON.stringify(tokensData ?? activeProject.figma_summary, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function tabBtnStyle(active: boolean): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "6px 12px",
    borderRadius: 8,
    border: "1px solid rgba(148,163,184,0.25)",
    background: active ? "#2563eb" : "rgba(30,41,59,0.7)",
    color: "#ffffff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  };
}
