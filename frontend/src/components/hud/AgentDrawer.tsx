import { Bot, Cpu, FileCode2, Send, Terminal, X } from "lucide-react";
import { useState } from "react";
import { useOfficeStore } from "../../store/officeStore";
import { normalizeOfficeAgents } from "../../utils/defaultAgents";
import { getStatusColor } from "../scene/officeLayout";

export function AgentDrawer() {
  const projects = useOfficeStore((s) => s.projects);
  const activeProjectId = useOfficeStore((s) => s.activeProjectId);
  const selectedAgentId = useOfficeStore((s) => s.selectedAgentId);
  const selectAgent = useOfficeStore((s) => s.selectAgent);
  const sendAgentChat = useOfficeStore((s) => s.sendAgentChat);

  const [chatText, setChatText] = useState("");
  const [sending, setSending] = useState(false);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;
  const agents = normalizeOfficeAgents(activeProject?.agents);
  const agent = selectedAgentId ? agents[selectedAgentId] ?? null : null;

  if (!agent) return null;

  const backendAgentId =
    activeProject && activeProject.agents[agent.id]
      ? agent.id
      : activeProject && agent.id === "dev" && activeProject.agents.ui_dev_2
        ? "ui_dev_2"
        : agent.id;

  const statusColor = getStatusColor(agent.status);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const msg = chatText.trim();
    if (!activeProject || !msg || sending) return;
    setSending(true);
    setChatText("");
    await sendAgentChat(activeProject.id, backendAgentId, msg);
    setSending(false);
  };

  return (
    <aside
      className="glass-panel"
      style={{
        position: "absolute",
        top: 76,
        right: 12,
        bottom: 78,
        width: 380,
        maxWidth: "calc(100vw - 24px)",
        zIndex: 25,
        borderRadius: 14,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 14px",
          borderBottom: "1px solid rgba(148,163,184,0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 999,
                background: statusColor,
                display: "inline-block",
              }}
            />
            <strong style={{ fontSize: 14 }}>{agent.name}</strong>
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
            {agent.title} · Vị trí: <code>{agent.location}</code>
          </div>
        </div>
        <button
          type="button"
          onClick={() => selectAgent(null, null)}
          style={{
            background: "transparent",
            border: "none",
            color: "#94a3b8",
            cursor: "pointer",
          }}
        >
          <X size={17} />
        </button>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 14,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {!activeProject && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 10,
              background: "rgba(59,130,246,0.14)",
              border: "1px solid rgba(59,130,246,0.35)",
              color: "#bfdbfe",
              fontSize: 12,
              lineHeight: 1.45,
            }}
          >
            Bạn đang xem <strong>Văn phòng mặc định</strong>. Bấm <strong>+ Dự án mới</strong> ở thanh trên để giao việc và mở chat trực tiếp với nhân viên.
          </div>
        )}
        {/* Execution Mode + Current Task */}
        <div
          style={{
            padding: 10,
            borderRadius: 10,
            background: "rgba(15,23,42,0.8)",
            border: "1px solid rgba(148,163,184,0.2)",
            fontSize: 12,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ color: "#94a3b8" }}>Trạng thái:</span>
            <span style={{ fontWeight: 700, color: statusColor }}>{agent.status}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ color: "#94a3b8" }}>Chế độ xử lý:</span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontWeight: 700,
                color: agent.execution_kind === "offline" ? "#34d399" : "#60a5fa",
              }}
            >
              {agent.execution_kind === "offline" ? <Cpu size={12} /> : <Bot size={12} />}
              {agent.execution_kind === "offline"
                ? "Offline 0-Token"
                : agent.execution_kind === "ai"
                ? "AI Agent"
                : "Idle"}
            </span>
          </div>
          <div style={{ color: "#e2e8f0", fontSize: 12 }}>
            {agent.current_task || agent.bubble_text || "Chưa có task"}
          </div>
        </div>

        {/* Edited Files */}
        {agent.edited_files.length > 0 && (
          <div>
            <div style={sectionTitleStyle}>
              <FileCode2 size={13} />
              <span>File đã tạo / chỉnh sửa</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {agent.edited_files.map((f) => (
                <code
                  key={f}
                  style={{
                    fontSize: 11,
                    padding: "3px 8px",
                    borderRadius: 6,
                    background: "rgba(30,41,59,0.9)",
                    border: "1px solid rgba(148,163,184,0.25)",
                    color: "#93c5fd",
                  }}
                >
                  {f}
                </code>
              ))}
            </div>
          </div>
        )}

        {/* Tool Calls */}
        {agent.tool_calls.length > 0 && (
          <div>
            <div style={sectionTitleStyle}>
              <Terminal size={13} />
              <span>Tool Calls ({agent.tool_calls.length})</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {agent.tool_calls.slice(-6).map((tc, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 11,
                    padding: "6px 8px",
                    borderRadius: 8,
                    background: "rgba(2,6,23,0.65)",
                    border: "1px solid rgba(148,163,184,0.18)",
                  }}
                >
                  <div style={{ fontWeight: 700, color: "#34d399" }}>{tc.name}</div>
                  {tc.args && (
                    <div style={{ color: "#94a3b8", wordBreak: "break-word", marginTop: 2 }}>
                      {typeof tc.args === "string" ? tc.args : JSON.stringify(tc.args)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Thoughts */}
        {agent.thoughts.length > 0 && (
          <div>
            <div style={sectionTitleStyle}>
              <Bot size={13} />
              <span>Nhật ký phân tích</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {agent.thoughts.slice(-6).map((t, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 11,
                    color: "#cbd5e1",
                    padding: "6px 8px",
                    borderRadius: 8,
                    background: "rgba(30,41,59,0.55)",
                  }}
                >
                  {t}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chat History */}
        {agent.chat_history.length > 0 && (
          <div>
            <div style={sectionTitleStyle}>Trao đổi trực tiếp</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {agent.chat_history.map((c, i) => (
                <div
                  key={i}
                  style={{
                    alignSelf: c.sender === "user" ? "flex-end" : "flex-start",
                    maxWidth: "90%",
                    fontSize: 12,
                    padding: "7px 10px",
                    borderRadius: 10,
                    background:
                      c.sender === "user"
                        ? "#2563eb"
                        : c.sender === "system"
                        ? "rgba(239,68,68,0.2)"
                        : "rgba(30,41,59,0.9)",
                    color: "#f8fafc",
                  }}
                >
                  {c.text}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Direct Chat Input */}
      <form
        onSubmit={handleSend}
        style={{
          padding: 10,
          borderTop: "1px solid rgba(148,163,184,0.2)",
          display: "flex",
          gap: 8,
        }}
      >
        <input
          value={chatText}
          onChange={(e) => setChatText(e.target.value)}
          disabled={!activeProject || sending}
          placeholder={
            activeProject
              ? `Nhắn chỉ dẫn cho ${agent.name}...`
              : "Tạo dự án mới để chat trực tiếp..."
          }
          style={{
            flex: 1,
            background: "#0f172a",
            color: "#f8fafc",
            border: "1px solid rgba(148,163,184,0.3)",
            borderRadius: 8,
            padding: "7px 10px",
            fontSize: 12,
            opacity: activeProject ? 1 : 0.6,
          }}
        />
        <button
          type="submit"
          disabled={!activeProject || sending}
          style={{
            background: activeProject ? "#2563eb" : "#334155",
            border: "none",
            color: "#ffffff",
            borderRadius: 8,
            padding: "0 12px",
            cursor: activeProject ? "pointer" : "not-allowed",
            display: "inline-flex",
            alignItems: "center",
          }}
        >
          <Send size={14} />
        </button>
      </form>
    </aside>
  );
}

const sectionTitleStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 11,
  fontWeight: 700,
  color: "#94a3b8",
  textTransform: "uppercase",
  marginBottom: 6,
};
