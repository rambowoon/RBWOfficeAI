import {
  Bug,
  ClipboardCheck,
  Cpu,
  Eye,
  Plus,
  RotateCcw,
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useOfficeStore } from "../../store/officeStore";
import type { ProjectPhase } from "../../types";

const PHASE_STEPS: Array<{ key: ProjectPhase[]; label: string }> = [
  { key: ["planning"], label: "Plan" },
  { key: ["waiting_plan_review"], label: "Duyệt Plan" },
  { key: ["offline_prep"], label: "Prep" },
  { key: ["seeding", "building_ui"], label: "UI & Seed" },
  { key: ["qa_testing", "re_testing"], label: "Pre-QA" },
  { key: ["waiting_bug_review"], label: "Duyệt Bug" },
  { key: ["fixing"], label: "Fix" },
  { key: ["completed"], label: "Done" },
];

export function TopBar() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const wsConnected = useOfficeStore((s) => s.wsConnected);
  const health = useOfficeStore((s) => s.health);
  const setActiveProjectId = useOfficeStore((s) => s.setActiveProjectId);
  const setShowNewProjectModal = useOfficeStore((s) => s.setShowNewProjectModal);
  const setShowPlanReview = useOfficeStore((s) => s.setShowPlanReview);
  const setShowBugBoard = useOfficeStore((s) => s.setShowBugBoard);
  const setShowPreviewDrawer = useOfficeStore((s) => s.setShowPreviewDrawer);
  const setFocusTarget = useOfficeStore((s) => s.setFocusTarget);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;
  const pendingBugs =
    activeProject?.bugs.filter(
      (b) => b.status === "pending_review" || b.status === "still_failing"
    ).length ?? 0;

  const isWaitingPlanReview = activeProject?.phase === "waiting_plan_review";
  const isWaitingReview = activeProject?.phase === "waiting_bug_review";

  return (
    <header
      className="glass-panel"
      style={{
        position: "absolute",
        top: 12,
        left: 12,
        right: 12,
        zIndex: 20,
        borderRadius: 14,
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        flexWrap: "wrap",
      }}
    >
      {/* Left: Brand & Project Selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontWeight: 800,
            fontSize: 14,
            color: "#f8fafc",
          }}
        >
          <Sparkles size={17} color="#3b82f6" />
          <span>RBWOfficeAI</span>
        </div>

        {projects.length > 0 && (
          <select
            value={activeProject?.id ?? ""}
            onChange={(e) => setActiveProjectId(e.target.value || null)}
            style={{
              background: "#0f172a",
              color: "#f1f5f9",
              border: "1px solid rgba(148,163,184,0.3)",
              borderRadius: 8,
              padding: "5px 10px",
              fontSize: 12,
              maxWidth: 210,
            }}
          >
            <option value="">✨ Văn phòng mặc định (4 người)</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.phase})
              </option>
            ))}
          </select>
        )}

        {activeProject && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: 999,
              background:
                activeProject.mode === "live_sdk"
                  ? "rgba(59,130,246,0.2)"
                  : "rgba(16,185,129,0.2)",
              color: activeProject.mode === "live_sdk" ? "#60a5fa" : "#34d399",
              border: "1px solid rgba(148,163,184,0.25)",
            }}
          >
            {activeProject.mode === "live_sdk" ? "Live Antigravity SDK" : "Demo 0-Token + Playwright"}
          </span>
        )}
      </div>

      {/* Center: Phase Stepper + Token Saver Meter */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {activeProject && (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {PHASE_STEPS.map((step) => {
              const active = step.key.includes(activeProject.phase);
              return (
                <span
                  key={step.label}
                  style={{
                    fontSize: 11,
                    fontWeight: active ? 700 : 500,
                    padding: "3px 8px",
                    borderRadius: 6,
                    background: active ? "#3b82f6" : "rgba(30,41,59,0.7)",
                    color: active ? "#ffffff" : "#94a3b8",
                  }}
                >
                  {step.label}
                </span>
              );
            })}
          </div>
        )}

        {activeProject && (
          <div
            title="Tách việc cố định chạy Offline 0-token thay vì đưa hết cho AI"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: 999,
              background: "rgba(16,185,129,0.14)",
              border: "1px solid rgba(16,185,129,0.35)",
              color: "#6ee7b7",
            }}
          >
            <Cpu size={13} />
            <span>
              Offline: <b>{activeProject.token_stats.offline_steps_completed}</b> · AI:{" "}
              <b>{activeProject.token_stats.ai_calls_made}</b> (Tiết kiệm{" "}
              {activeProject.token_stats.estimated_tokens_saved_pct}%)
            </span>
          </div>
        )}
      </div>

      {/* Right: Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          title={
            wsConnected
              ? `WS Connected · SDK: ${health?.sdk.available ? "Ready" : "Unavailable"}`
              : "WebSocket reconnecting"
          }
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            color: wsConnected ? "#34d399" : "#f87171",
            padding: "0 4px",
          }}
        >
          {wsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
        </span>

        <button
          type="button"
          title="Đưa camera về toàn cảnh"
          onClick={() => setFocusTarget([0, 0.5, 0])}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            background: "rgba(30,41,59,0.8)",
            color: "#cbd5e1",
            border: "1px solid rgba(148,163,184,0.25)",
            borderRadius: 8,
            padding: "6px 10px",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          <RotateCcw size={13} />
        </button>

        {activeProject && (
          <>
            {(isWaitingPlanReview || Boolean(activeProject.leader_plan_markdown)) && (
              <button
                type="button"
                className={isWaitingPlanReview ? "pulse-amber" : ""}
                onClick={() => setShowPlanReview(true)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  background: isWaitingPlanReview ? "#f59e0b" : "rgba(30,41,59,0.9)",
                  color: isWaitingPlanReview ? "#0f172a" : "#f1f5f9",
                  border: "1px solid rgba(56,189,248,0.45)",
                  borderRadius: 8,
                  padding: "6px 11px",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                <ClipboardCheck size={14} />
                <span>{isWaitingPlanReview ? "Duyệt Đặc Tả" : "Đặc tả Leader"}</span>
              </button>
            )}

            <button
              type="button"
              className={isWaitingReview ? "pulse-amber" : ""}
              onClick={() => setShowBugBoard(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: isWaitingReview ? "#f59e0b" : "rgba(30,41,59,0.9)",
                color: isWaitingReview ? "#0f172a" : "#f1f5f9",
                border: "1px solid rgba(245,158,11,0.45)",
                borderRadius: 8,
                padding: "6px 11px",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              <Bug size={14} />
              <span>Bug Board {pendingBugs > 0 ? `(${pendingBugs})` : ""}</span>
            </button>

            <button
              type="button"
              onClick={() => setShowPreviewDrawer(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "rgba(30,41,59,0.9)",
                color: "#e2e8f0",
                border: "1px solid rgba(148,163,184,0.3)",
                borderRadius: 8,
                padding: "6px 11px",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Eye size={14} />
              <span>Preview & Tokens</span>
            </button>
          </>
        )}

        <button
          type="button"
          onClick={() => setShowNewProjectModal(true)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: 8,
            padding: "7px 13px",
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <Plus size={14} />
          <span>Dự án mới</span>
        </button>
      </div>
    </header>
  );
}
