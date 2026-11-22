import type { AgentState } from "../types";

export function buildFallbackAgents(): Record<string, AgentState> {
  const defs: Array<{ id: string; name: string; role: AgentState["role"]; title: string }> = [
    { id: "leader", name: "Minh (Leader)", role: "leader", title: "Tech Lead & Architect" },
    { id: "asset", name: "Linh (Assets & Config)", role: "asset", title: "Config, Font/WebP & Seed" },
    { id: "dev", name: "Vy (UI & Frontend)", role: "dev", title: "HTML/Blade, CSS & Responsive" },
    { id: "qa", name: "Tuấn (QA & Tester)", role: "qa", title: "Static & Playwright QA" },
  ];

  const record: Record<string, AgentState> = {};
  for (const d of defs) {
    record[d.id] = {
      id: d.id,
      name: d.name,
      role: d.role,
      title: d.title,
      status: "idle",
      location: d.role === "leader" ? "leader_desk" : "desk",
      current_task: "",
      bubble_text: "",
      execution_kind: "idle",
      edited_files: [],
      thoughts: [],
      tool_calls: [],
      chat_history: [],
    };
  }
  return record;
}

export function isFourAgentRoster(agents: Record<string, AgentState> | undefined): boolean {
  if (!agents) return false;
  return (
    Object.keys(agents).length === 4 &&
    "leader" in agents &&
    "asset" in agents &&
    "dev" in agents &&
    "qa" in agents
  );
}

export function normalizeOfficeAgents(
  agents: Record<string, AgentState> | undefined
): Record<string, AgentState> {
  if (!agents) {
    return buildFallbackAgents();
  }
  if (isFourAgentRoster(agents)) {
    return agents;
  }

  const fallback = buildFallbackAgents();
  const leaderAgent = agents.leader ?? fallback.leader;
  const assetAgent = agents.asset ?? fallback.asset;
  const devAgent =
    agents.dev ??
    (agents.ui_dev_2
      ? {
          ...agents.ui_dev_2,
          id: "dev",
          role: "dev" as const,
          name: "Vy (UI & Frontend)",
        }
      : fallback.dev);
  const qaAgent = agents.qa
    ? { ...agents.qa, name: "Tuấn (QA & Tester)" }
    : fallback.qa;

  return {
    leader: leaderAgent,
    asset: assetAgent,
    dev: devAgent,
    qa: qaAgent,
  };
}
