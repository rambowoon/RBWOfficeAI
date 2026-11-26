import { create } from "zustand";
import { isFourAgentRoster } from "../utils/defaultAgents";
import type {
  AgentState,
  BugReviewRequest,
  HealthInfo,
  PlanApprovalRequest,
  ProjectCreatePayload,
  ProjectState,
} from "../types";

export type AvatarModelStyle = "rpm" | "chibi";

interface OfficeStore {
  projects: ProjectState[];
  activeProjectId: string | null;
  selectedAgentId: string | null;
  showNewProjectModal: boolean;
  showPlanReview: boolean;
  showBugBoard: boolean;
  showPreviewDrawer: boolean;
  isBreakTime: boolean;
  avatarModelStyle: AvatarModelStyle;
  focusTarget: [number, number, number] | null;
  health: HealthInfo | null;
  wsConnected: boolean;
  isSubmitting: boolean;
  lastError: string | null;
  _lastAutoPlanKey: string | null;
  _lastAutoBugKey: string | null;
  _ws: WebSocket | null;

  fetchHealth: () => Promise<void>;
  fetchProjects: () => Promise<void>;
  connectWebSocket: () => void;
  createProject: (payload: ProjectCreatePayload) => Promise<ProjectState | null>;
  retryProject: (projectId: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  approveLeaderPlan: (projectId: string, req: PlanApprovalRequest) => Promise<void>;
  submitBugReview: (projectId: string, req: BugReviewRequest) => Promise<void>;
  sendAgentChat: (projectId: string, agentId: string, message: string) => Promise<void>;
  setActiveProjectId: (id: string | null) => void;
  selectAgent: (agentId: string | null, focus?: [number, number, number] | null) => void;
  setShowNewProjectModal: (v: boolean) => void;
  setShowPlanReview: (v: boolean) => void;
  setShowBugBoard: (v: boolean) => void;
  setShowPreviewDrawer: (v: boolean) => void;
  toggleBreakTime: () => void;
  setAvatarModelStyle: (style: AvatarModelStyle) => void;
  setFocusTarget: (target: [number, number, number] | null) => void;
  clearError: () => void;
}

function upsertProject(list: ProjectState[], incoming: ProjectState): ProjectState[] {
  const idx = list.findIndex((p) => p.id === incoming.id);
  if (idx === -1) {
    return [incoming, ...list];
  }
  const copy = [...list];
  copy[idx] = incoming;
  return copy;
}

export const useOfficeStore = create<OfficeStore>((set, get) => ({
  projects: [],
  activeProjectId: null,
  selectedAgentId: null,
  showNewProjectModal: false,
  showPlanReview: false,
  showBugBoard: false,
  showPreviewDrawer: false,
  isBreakTime: false,
  avatarModelStyle: "rpm",
  focusTarget: null,
  health: null,
  wsConnected: false,
  isSubmitting: false,
  lastError: null,
  _lastAutoPlanKey: null,
  _lastAutoBugKey: null,
  _ws: null,

  fetchHealth: async () => {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) return;
      const data = (await res.json()) as HealthInfo;
      set({ health: data });
    } catch {
      // ignore transient startup poll error
    }
  },

  fetchProjects: async () => {
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) return;
      const list = (await res.json()) as ProjectState[];
      const first = list[0];
      const validRoster = isFourAgentRoster(first?.agents);
      set((s) => ({
        projects: list,
        activeProjectId: s.activeProjectId ?? (validRoster && first ? first.id : null),
      }));
    } catch {
      // handled by WS / retry
    }
  },

  connectWebSocket: () => {
    const existing = get()._ws;
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set({ wsConnected: true });
    };

    ws.onclose = () => {
      set({ wsConnected: false, _ws: null });
      window.setTimeout(() => {
        get().connectWebSocket();
      }, 2200);
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data) as {
          type: string;
          project_id: string | null;
          payload: Record<string, unknown>;
        };

        if (msg.type === "snapshot") {
          const projects = (msg.payload.projects as ProjectState[]) || [];
          const first = projects[0];
          const validRoster = isFourAgentRoster(first?.agents);
          set((s) => ({
            projects,
            activeProjectId: s.activeProjectId ?? (validRoster && first ? first.id : null),
          }));
          return;
        }

        if (msg.type === "project_sync" && msg.payload.project) {
          const project = msg.payload.project as ProjectState;
          const activeId = get().activeProjectId ?? project.id;
          const planKey = `${project.id}:plan`;
          const bugKey = `${project.id}:${project.qa_round}`;
          const shouldAutoOpenPlan =
            project.id === activeId &&
            project.phase === "waiting_plan_review" &&
            get()._lastAutoPlanKey !== planKey;
          const shouldAutoOpenBug =
            project.id === activeId &&
            project.phase === "waiting_bug_review" &&
            get()._lastAutoBugKey !== bugKey;

          set((s) => ({
            projects: upsertProject(s.projects, project),
            activeProjectId: s.activeProjectId ?? project.id,
            showPlanReview: shouldAutoOpenPlan ? true : s.showPlanReview,
            showBugBoard: shouldAutoOpenBug ? true : s.showBugBoard,
            _lastAutoPlanKey: shouldAutoOpenPlan ? planKey : s._lastAutoPlanKey,
            _lastAutoBugKey: shouldAutoOpenBug ? bugKey : s._lastAutoBugKey,
          }));
          return;
        }

        if (msg.type === "project_deleted" && msg.project_id) {
          set((s) => {
            const remaining = s.projects.filter((p) => p.id !== msg.project_id);
            return {
              projects: remaining,
              activeProjectId:
                s.activeProjectId === msg.project_id
                  ? remaining[0]?.id ?? null
                  : s.activeProjectId,
            };
          });
          return;
        }

        if (msg.type === "agent_update" && msg.project_id && msg.payload.agent) {
          const agent = msg.payload.agent as AgentState;
          set((s) => ({
            projects: s.projects.map((p) =>
              p.id === msg.project_id
                ? { ...p, agents: { ...p.agents, [agent.id]: agent } }
                : p
            ),
          }));
        }
      } catch {
        // ignore malformed frames
      }
    };

    set({ _ws: ws });
  },

  createProject: async (payload) => {
    set({ isSubmitting: true, lastError: null, isBreakTime: false });
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Create project failed" }));
        throw new Error(err.detail || "Create project failed");
      }
      const created = (await res.json()) as ProjectState;
      set((s) => ({
        projects: upsertProject(s.projects, created),
        activeProjectId: created.id,
        showNewProjectModal: false,
        showPlanReview: false,
        showBugBoard: false,
        isSubmitting: false,
      }));
      return created;
    } catch (e) {
      set({
        isSubmitting: false,
        lastError: e instanceof Error ? e.message : "Không thể tạo dự án",
      });
      return null;
    }
  },

  retryProject: async (projectId) => {
    set({ isSubmitting: true, lastError: null, isBreakTime: false });
    try {
      const res = await fetch(`/api/projects/${projectId}/retry`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Retry project failed" }));
        throw new Error(err.detail || "Retry project failed");
      }
      const updated = (await res.json()) as ProjectState;
      set((s) => ({
        projects: upsertProject(s.projects, updated),
        activeProjectId: updated.id,
        showPlanReview: false,
        showBugBoard: false,
        _lastAutoPlanKey: null,
        _lastAutoBugKey: null,
        isSubmitting: false,
      }));
    } catch (e) {
      set({
        isSubmitting: false,
        lastError: e instanceof Error ? e.message : "Không thể chạy lại dự án",
      });
    }
  },

  deleteProject: async (projectId) => {
    set({ isSubmitting: true, lastError: null });
    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Delete project failed" }));
        throw new Error(err.detail || "Delete project failed");
      }
      set((s) => {
        const remaining = s.projects.filter((p) => p.id !== projectId);
        return {
          projects: remaining,
          activeProjectId:
            s.activeProjectId === projectId ? remaining[0]?.id ?? null : s.activeProjectId,
          showPlanReview: false,
          showBugBoard: false,
          showPreviewDrawer: false,
          isSubmitting: false,
        };
      });
    } catch (e) {
      set({
        isSubmitting: false,
        lastError: e instanceof Error ? e.message : "Không thể xóa dự án",
      });
    }
  },

  approveLeaderPlan: async (projectId, req) => {
    set({ isSubmitting: true, lastError: null, isBreakTime: false });
    try {
      const res = await fetch(`/api/projects/${projectId}/plan/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Approve plan failed" }));
        throw new Error(err.detail || "Approve plan failed");
      }
      const updated = (await res.json()) as ProjectState;
      set((s) => ({
        projects: upsertProject(s.projects, updated),
        showPlanReview: false,
        isSubmitting: false,
      }));
    } catch (e) {
      set({
        isSubmitting: false,
        lastError: e instanceof Error ? e.message : "Lỗi duyệt đặc tả Leader",
      });
    }
  },

  submitBugReview: async (projectId, req) => {
    set({ isSubmitting: true, lastError: null, isBreakTime: false });
    try {
      const res = await fetch(`/api/projects/${projectId}/bugs/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Submit bug review failed" }));
        throw new Error(err.detail || "Submit bug review failed");
      }
      const updated = (await res.json()) as ProjectState;
      set((s) => ({
        projects: upsertProject(s.projects, updated),
        showBugBoard: false,
        isSubmitting: false,
      }));
    } catch (e) {
      set({
        isSubmitting: false,
        lastError: e instanceof Error ? e.message : "Lỗi gửi duyệt bug",
      });
    }
  },

  sendAgentChat: async (projectId, agentId, message) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/agents/${agentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) return;
      const updatedAgent = (await res.json()) as AgentState;
      set((s) => ({
        projects: s.projects.map((p) =>
          p.id === projectId
            ? { ...p, agents: { ...p.agents, [updatedAgent.id]: updatedAgent } }
            : p
        ),
      }));
    } catch (e) {
      set({ lastError: e instanceof Error ? e.message : "Lỗi gửi tin nhắn" });
    }
  },

  setActiveProjectId: (id) => set({ activeProjectId: id }),

  selectAgent: (agentId, focus = null) =>
    set({
      selectedAgentId: agentId,
      focusTarget: focus ?? null,
    }),

  setShowNewProjectModal: (v) => set({ showNewProjectModal: v }),
  setShowPlanReview: (v) => set({ showPlanReview: v }),
  setShowBugBoard: (v) => set({ showBugBoard: v }),
  setShowPreviewDrawer: (v) => set({ showPreviewDrawer: v }),
  toggleBreakTime: () =>
    set((s) => ({
      isBreakTime: !s.isBreakTime,
      focusTarget: !s.isBreakTime ? [6.8, 0.8, 3.8] : [0, 0.6, 0],
    })),
  setAvatarModelStyle: (style) => set({ avatarModelStyle: style }),
  setFocusTarget: (target) => set({ focusTarget: target }),
  clearError: () => set({ lastError: null }),
}));
