import { Bug, CheckCircle2, Cpu, ShieldCheck, Wrench, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useOfficeStore } from "../../store/officeStore";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";

export function BugBoardDrawer() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const show = useOfficeStore((s) => s.showBugBoard);
  const setShow = useOfficeStore((s) => s.setShowBugBoard);
  const submitBugReview = useOfficeStore((s) => s.submitBugReview);
  const isSubmitting = useOfficeStore((s) => s.isSubmitting);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  useEffect(() => {
    if (!activeProject) return;
    const nextSel: Record<string, boolean> = {};
    const nextNotes: Record<string, string> = {};
    for (const b of activeProject.bugs) {
      if (b.status === "pending_review" || b.status === "still_failing") {
        nextSel[b.id] = b.severity !== "minor";
      }
      nextNotes[b.id] = b.user_note || "";
    }
    setSelectedIds(nextSel);
    setNotes(nextNotes);
  }, [activeProject?.id, activeProject?.qa_round, activeProject?.phase]);

  if (!show || !activeProject) return null;

  const actionableBugs = activeProject.bugs.filter(
    (b) => b.status === "pending_review" || b.status === "still_failing"
  );
  const resolvedBugs = activeProject.bugs.filter(
    (b) => b.status === "fixed" || b.status === "ignored"
  );
  const agentsMap = normalizeOfficeAgents(activeProject.agents);
  const isWaitingReview = activeProject.phase === "waiting_bug_review";
  const selectedCount = actionableBugs.filter((b) => selectedIds[b.id]).length;

  const handleAction = async (mode: "fix_selected" | "skip_and_complete") => {
    const decisions = actionableBugs.map((b) => ({
      bug_id: b.id,
      action: (mode === "fix_selected" && selectedIds[b.id] ? "fix" : "ignore") as
        | "fix"
        | "ignore",
      user_note: notes[b.id] || "",
    }));
    await submitBugReview(activeProject.id, {
      decisions,
      action_mode: mode,
    });
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 45,
        background: "rgba(2,6,23,0.65)",
        backdropFilter: "blur(5px)",
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: 680,
          maxWidth: "100vw",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          borderLeft: "1px solid rgba(148,163,184,0.25)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid rgba(148,163,184,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Bug size={18} color="#f59e0b" />
              <strong style={{ fontSize: 16 }}>
                Bug Board — Duyệt lỗi trước khi giao Dev Fix
              </strong>
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
              QA Vòng #{activeProject.qa_round} · Tổng {activeProject.bugs.length} mục (
              {actionableBugs.length} chờ duyệt, {resolvedBugs.length} đã xử lý)
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShow(false)}
            style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
          >
            <X size={19} />
          </button>
        </div>

        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 18,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {/* Real Playwright Screenshots Strip */}
          {Object.keys(activeProject.screenshots).length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 8 }}>
                Ảnh chụp thực tế từ Playwright (0-Token) — Bấm để phóng to
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                {Object.entries(activeProject.screenshots).map(([vp, url]) => (
                  <button
                    key={vp}
                    type="button"
                    onClick={() => setZoomImg(url)}
                    style={{
                      padding: 6,
                      borderRadius: 10,
                      background: "#0f172a",
                      border: "1px solid rgba(148,163,184,0.25)",
                      color: "#e2e8f0",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <img
                      src={url}
                      alt={vp}
                      style={{
                        width: "100%",
                        height: 110,
                        objectFit: "cover",
                        objectPosition: "top",
                        borderRadius: 6,
                      }}
                    />
                    <div style={{ fontSize: 11, fontWeight: 700, marginTop: 4, textTransform: "uppercase" }}>
                      {vp}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Actionable Bugs Checklist */}
          {actionableBugs.length > 0 ? (
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 700, color: "#fbbf24" }}>
                  Danh sách lỗi cần bạn duyệt ({actionableBugs.length})
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => {
                      const all: Record<string, boolean> = {};
                      actionableBugs.forEach((b) => (all[b.id] = true));
                      setSelectedIds(all);
                    }}
                    style={miniBtnStyle}
                  >
                    Chọn tất cả
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedIds({})}
                    style={miniBtnStyle}
                  >
                    Bỏ chọn hết
                  </button>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {actionableBugs.map((bug) => {
                  const checked = !!selectedIds[bug.id];
                  return (
                    <div
                      key={bug.id}
                      style={{
                        padding: 12,
                        borderRadius: 12,
                        background: checked ? "rgba(245,158,11,0.1)" : "rgba(15,23,42,0.75)",
                        border: checked
                          ? "1px solid rgba(245,158,11,0.55)"
                          : "1px solid rgba(148,163,184,0.22)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      <label
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 10,
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            setSelectedIds((prev) => ({ ...prev, [bug.id]: e.target.checked }))
                          }
                          style={{ marginTop: 3 }}
                        />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                            <strong style={{ fontSize: 13 }}>{bug.title}</strong>
                            <span style={badgeStyle(bug.severity)}>{bug.severity}</span>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                fontSize: 10,
                                padding: "2px 7px",
                                borderRadius: 999,
                                background: "rgba(16,185,129,0.16)",
                                color: "#6ee7b7",
                              }}
                            >
                              <Cpu size={10} />
                              {bug.source === "offline_static"
                                ? "0-Token Static"
                                : bug.source === "ai_vision"
                                  ? "AI Vision QA"
                                  : "0-Token Playwright"}
                            </span>
                            <span style={{ fontSize: 10, color: "#94a3b8" }}>
                              Viewport: {bug.viewport} · Giao:{" "}
                              {agentsMap[bug.assigned_role]?.name ??
                                (bug.assigned_role === "asset"
                                  ? "Linh (Assets & Config)"
                                  : "Vy (UI & Frontend)")}
                            </span>
                          </div>
                          <p style={{ margin: "5px 0", fontSize: 12, color: "#cbd5e1" }}>
                            {bug.description}
                          </p>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>
                            File: <code>{bug.file_path || "-"}</code> · Rule/Selector:{" "}
                            <code>{bug.selector_or_rule || "-"}</code>
                          </div>
                        </div>
                      </label>

                      <input
                        value={notes[bug.id] || ""}
                        onChange={(e) =>
                          setNotes((prev) => ({ ...prev, [bug.id]: e.target.value }))
                        }
                        placeholder="Ghi chú thêm cho Dev (tuỳ chọn)..."
                        style={{
                          width: "100%",
                          background: "#0f172a",
                          color: "#f1f5f9",
                          border: "1px solid rgba(148,163,184,0.25)",
                          borderRadius: 8,
                          padding: "6px 10px",
                          fontSize: 11,
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: 18,
                borderRadius: 12,
                background: "rgba(16,185,129,0.12)",
                border: "1px solid rgba(16,185,129,0.35)",
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 13,
              }}
            >
              <CheckCircle2 size={18} color="#34d399" />
              <span>Không còn lỗi nào đang chờ duyệt!</span>
            </div>
          )}

          {/* Resolved / Ignored History */}
          {resolvedBugs.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8", marginBottom: 8 }}>
                Lịch sử đã xử lý ({resolvedBugs.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {resolvedBugs.map((b) => (
                  <div
                    key={b.id}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: "rgba(15,23,42,0.65)",
                      border: "1px solid rgba(148,163,184,0.18)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 12,
                    }}
                  >
                    <span>{b.title}</span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: b.status === "fixed" ? "#34d399" : "#94a3b8",
                      }}
                    >
                      {b.status === "fixed" ? "✅ Đã sửa sạch" : "⏭️ Đã bỏ qua"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {isWaitingReview && (
          <div
            style={{
              padding: "14px 18px",
              borderTop: "1px solid rgba(148,163,184,0.2)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 10,
            }}
          >
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => handleAction("skip_and_complete")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "rgba(30,41,59,0.9)",
                color: "#cbd5e1",
                border: "1px solid rgba(148,163,184,0.3)",
                borderRadius: 8,
                padding: "9px 14px",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              <ShieldCheck size={15} />
              <span>Bỏ qua lỗi & Hoàn thành</span>
            </button>

            <button
              type="button"
              disabled={isSubmitting || selectedCount === 0}
              onClick={() => handleAction("fix_selected")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: selectedCount > 0 ? "#f59e0b" : "#475569",
                color: "#0f172a",
                border: "none",
                borderRadius: 8,
                padding: "9px 16px",
                fontSize: 12,
                fontWeight: 800,
                cursor: selectedCount > 0 ? "pointer" : "not-allowed",
              }}
            >
              <Wrench size={15} />
              <span>Giao Dev Fix ({selectedCount} lỗi đã chọn)</span>
            </button>
          </div>
        )}
      </div>

      {/* Screenshot Lightbox */}
      {zoomImg && (
        <div
          onClick={() => setZoomImg(null)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 60,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            cursor: "zoom-out",
          }}
        >
          <img
            src={zoomImg}
            alt="Zoomed screenshot"
            style={{ maxWidth: "95%", maxHeight: "95%", borderRadius: 10 }}
          />
        </div>
      )}
    </div>
  );
}

const miniBtnStyle: React.CSSProperties = {
  background: "rgba(30,41,59,0.8)",
  color: "#cbd5e1",
  border: "1px solid rgba(148,163,184,0.25)",
  borderRadius: 6,
  padding: "3px 9px",
  fontSize: 11,
  cursor: "pointer",
};

function badgeStyle(severity: string): React.CSSProperties {
  const bg =
    severity === "critical"
      ? "rgba(239,68,68,0.22)"
      : severity === "major"
      ? "rgba(245,158,11,0.22)"
      : "rgba(148,163,184,0.22)";
  const color =
    severity === "critical" ? "#fca5a5" : severity === "major" ? "#fcd34d" : "#cbd5e1";
  return {
    fontSize: 10,
    fontWeight: 700,
    padding: "2px 7px",
    borderRadius: 999,
    background: bg,
    color,
    textTransform: "uppercase",
  };
}
