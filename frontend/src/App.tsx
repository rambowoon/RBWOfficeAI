import { useEffect } from "react";
import { AgentDrawer } from "./components/hud/AgentDrawer";
import { BottomRoster } from "./components/hud/BottomRoster";
import { BugBoardDrawer } from "./components/hud/BugBoardDrawer";
import { NewProjectModal } from "./components/hud/NewProjectModal";
import { PlanReviewDrawer } from "./components/hud/PlanReviewDrawer";
import { PreviewDrawer } from "./components/hud/PreviewDrawer";
import { TopBar } from "./components/hud/TopBar";
import { OfficeScene } from "./components/scene/OfficeScene";
import { useOfficeStore } from "./store/officeStore";

export default function App() {
  const fetchHealth = useOfficeStore((s) => s.fetchHealth);
  const fetchProjects = useOfficeStore((s) => s.fetchProjects);
  const connectWebSocket = useOfficeStore((s) => s.connectWebSocket);
  const projects = useOfficeStore((s) => s.projects);
  const setShowNewProjectModal = useOfficeStore((s) => s.setShowNewProjectModal);

  useEffect(() => {
    fetchHealth();
    fetchProjects();
    connectWebSocket();
  }, [fetchHealth, fetchProjects, connectWebSocket]);

  return (
    <main style={{ width: "100vw", height: "100vh", position: "relative", overflow: "hidden" }}>
      <OfficeScene />
      <TopBar />

      {projects.length === 0 && (
        <div
          className="glass-panel"
          style={{
            position: "absolute",
            top: 126,
            left: 12,
            zIndex: 18,
            borderRadius: 12,
            padding: "12px 16px",
            maxWidth: 340,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
            Văn phòng 3D đã sẵn sàng!
          </div>
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 10 }}>
            Bấm <b>Dự án mới</b> để giao đặc tả + link Figma cho Leader phân việc và chạy kiểm thử
            Playwright tự động.
          </div>
          <button
            type="button"
            onClick={() => setShowNewProjectModal(true)}
            style={{
              background: "#2563eb",
              border: "none",
              color: "#ffffff",
              borderRadius: 8,
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            + Tạo dự án đầu tiên
          </button>
        </div>
      )}

      <AgentDrawer />
      <BottomRoster />
      <NewProjectModal />
      <PlanReviewDrawer />
      <BugBoardDrawer />
      <PreviewDrawer />
    </main>
  );
}
