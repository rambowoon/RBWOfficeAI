import { CheckCircle2, ClipboardCheck, RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useOfficeStore } from "../../store/officeStore";
import type { PlanTaskUpdate } from "../../types";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";

export function PlanReviewDrawer() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const show = useOfficeStore((s) => s.showPlanReview);
  const setShow = useOfficeStore((s) => s.setShowPlanReview);
  const approveLeaderPlan = useOfficeStore((s) => s.approveLeaderPlan);
  const isSubmitting = useOfficeStore((s) => s.isSubmitting);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const [planMarkdown, setPlanMarkdown] = useState("");
  const [taskEdits, setTaskEdits] = useState<PlanTaskUpdate[]>([]);
  const [userNote, setUserNote] = useState("");

  useEffect(() => {
    if (!activeProject) return;
    setPlanMarkdown(activeProject.leader_plan_markdown ?? "");
    setTaskEdits(
      activeProject.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        detail: t.detail ?? "",
      }))
    );
    setUserNote(activeProject.plan_review_note ?? "");
  }, [
    activeProject?.id,
    activeProject?.leader_plan_markdown,
    activeProject?.phase,
  ]);

  if (!show || !activeProject) return null;

  const isWaitingPlan = activeProject.phase === "waiting_plan_review";
  const agentsMap = normalizeOfficeAgents(activeProject.agents);
  const figmaSummary = activeProject.figma_summary as {
    file_name?: string;
    colors_count?: number;
    fonts?: string[];
    sections_count?: number;
    stats?: { compression_pct?: number; kept_node_count?: number; raw_node_count?: number };
  };

  const handleResetDefault = () => {
    setPlanMarkdown(activeProject.leader_plan_markdown ?? "");
    setTaskEdits(
      activeProject.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        detail: t.detail ?? "",
      }))
    );
  };

  const handleApprove = async () => {
    if (!planMarkdown.trim() || isSubmitting) return;
    await approveLeaderPlan(activeProject.id, {
      leader_plan_markdown: planMarkdown.trim(),
      tasks: taskEdits,
      user_note: userNote.trim(),
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
          width: 720,
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
            gap: 10,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <ClipboardCheck size={18} color="#38bdf8" />
              <strong style={{ fontSize: 16 }}>
                Đặc tả phân tích của Minh (Leader)
              </strong>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: isWaitingPlan
                    ? "rgba(245,158,11,0.2)"
                    : "rgba(16,185,129,0.2)",
                  color: isWaitingPlan ? "#fbbf24" : "#34d399",
                  border: isWaitingPlan
                    ? "1px solid rgba(245,158,11,0.5)"
                    : "1px solid rgba(16,185,129,0.45)",
                }}
              >
                {isWaitingPlan ? "Chờ bạn xem & duyệt" : "Đã duyệt & giao team"}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
              Dự án: <b>{activeProject.name}</b> · Framework:{" "}
              <code>{activeProject.framework}</code>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShow(false)}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
            }}
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
          {/* Figma Tokens Summary */}
          <div
            style={{
              padding: 12,
              borderRadius: 12,
              background: "rgba(15,23,42,0.75)",
              border: "1px solid rgba(56,189,248,0.28)",
              fontSize: 12,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 10,
            }}
          >
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Figma File
              </div>
              <div style={{ fontWeight: 700, color: "#f8fafc", marginTop: 2 }}>
                {figmaSummary?.file_name || "Design System"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Nén Node Rác (0 Token)
              </div>
              <div style={{ fontWeight: 700, color: "#34d399", marginTop: 2 }}>
                {figmaSummary?.stats?.compression_pct ?? 0}% ({figmaSummary?.sections_count ?? 0}{" "}
                sections)
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 10, textTransform: "uppercase" }}>
                Fonts & Màu
              </div>
              <div style={{ fontWeight: 600, color: "#cbd5e1", marginTop: 2 }}>
                {(figmaSummary?.fonts || []).join(", ") || "Be Vietnam Pro"} ·{" "}
                {figmaSummary?.colors_count ?? 0} màu
              </div>
            </div>
          </div>

          {/* Editable Leader Analyzed Specification */}
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 6,
                gap: 8,
              }}
            >
              <span style={{ fontSize: 12, fontWeight: 700, color: "#93c5fd" }}>
                Nội dung đặc tả Leader đã phân tích (bạn có thể chỉnh sửa trực tiếp trước khi giao việc)
              </span>
              {isWaitingPlan && (
                <button
                  type="button"
                  onClick={handleResetDefault}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 11,
                    padding: "4px 9px",
                    borderRadius: 7,
                    background: "rgba(30,41,59,0.9)",
                    color: "#cbd5e1",
                    border: "1px solid rgba(148,163,184,0.3)",
                    cursor: "pointer",
                  }}
                >
                  <RotateCcw size={11} />
                  <span>Khôi phục bản gốc của Leader</span>
                </button>
              )}
            </div>
            <textarea
              value={planMarkdown}
              readOnly={!isWaitingPlan}
              onChange={(e) => setPlanMarkdown(e.target.value)}
              rows={12}
              style={{
                width: "100%",
                minHeight: 240,
                background: "#0f172a",
                color: "#f8fafc",
                border: isWaitingPlan
                  ? "1px solid rgba(56,189,248,0.45)"
                  : "1px solid rgba(148,163,184,0.22)",
                borderRadius: 10,
                padding: 12,
                fontSize: 12,
                lineHeight: 1.55,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                resize: "vertical",
              }}
            />
          </div>

          {/* Editable 3-Staff Task Breakdown */}
          {taskEdits.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 8 }}>
                Phân công dự kiến xuống 3 nhân viên (Linh → Vy → Tuấn)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {taskEdits.map((task, idx) => {
                  const orig = activeProject.tasks[idx];
                  const assigneeName =
                    (orig && agentsMap[orig.owner_role]?.name) || orig?.owner_role || "Nhân viên";
                  return (
                    <div
                      key={task.id}
                      style={{
                        padding: 10,
                        borderRadius: 10,
                        background: "rgba(15,23,42,0.75)",
                        border: "1px solid rgba(148,163,184,0.22)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                        <strong style={{ color: "#38bdf8" }}>
                          Bước {idx + 1}: {assigneeName}
                        </strong>
                        {orig && (
                          <span style={{ color: "#94a3b8" }}>Trạng thái: {orig.status}</span>
                        )}
                      </div>
                      <input
                        value={task.title}
                        readOnly={!isWaitingPlan}
                        onChange={(e) =>
                          setTaskEdits((prev) =>
                            prev.map((item) =>
                              item.id === task.id ? { ...item, title: e.target.value } : item
                            )
                          )
                        }
                        style={fieldStyle}
                      />
                      <input
                        value={task.detail}
                        readOnly={!isWaitingPlan}
                        placeholder="Mô tả chi tiết phạm vi đầu việc..."
                        onChange={(e) =>
                          setTaskEdits((prev) =>
                            prev.map((item) =>
                              item.id === task.id ? { ...item, detail: e.target.value } : item
                            )
                          )
                        }
                        style={{ ...fieldStyle, color: "#cbd5e1", fontSize: 11 }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Optional Note */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#cbd5e1", marginBottom: 6 }}>
              Ghi chú chỉ đạo thêm cho nhân viên (tuỳ chọn)
            </div>
            <input
              value={userNote}
              readOnly={!isWaitingPlan}
              onChange={(e) => setUserNote(e.target.value)}
              placeholder="Ví dụ: Nhấn mạnh bảng giá ở Hero, ưu tiên font Be Vietnam Pro..."
              style={fieldStyle}
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid rgba(148,163,184,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
          }}
        >
          {isWaitingPlan ? (
            <>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>
                Nhân viên chỉ bắt đầu chạy sau khi bạn bấm duyệt bản đặc tả này.
              </div>
              <button
                type="button"
                disabled={isSubmitting || !planMarkdown.trim()}
                onClick={handleApprove}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  background: "#10b981",
                  border: "none",
                  color: "#0f172a",
                  borderRadius: 9,
                  padding: "9px 16px",
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: isSubmitting ? "wait" : "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                <Sparkles size={15} />
                <span>
                  {isSubmitting ? "Đang giao việc..." : "✅ Duyệt & Giao nhân viên làm"}
                </span>
              </button>
            </>
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#34d399",
                fontWeight: 700,
              }}
            >
              <CheckCircle2 size={16} />
              <span>Đã duyệt đặc tả — Nhân viên đang/đã triển khai theo kế hoạch này.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const fieldStyle: React.CSSProperties = {
  width: "100%",
  background: "#0f172a",
  color: "#f8fafc",
  border: "1px solid rgba(148,163,184,0.28)",
  borderRadius: 7,
  padding: "6px 9px",
  fontSize: 12,
};
