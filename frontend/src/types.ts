export type AgentRole =
  | "leader"
  | "dev"
  | "config"
  | "asset"
  | "ui_dev_1"
  | "ui_dev_2"
  | "seeder"
  | "qa";

export type AgentVisualStatus =
  | "idle"
  | "walking"
  | "working_offline"
  | "working_ai"
  | "meeting_leader"
  | "waiting_review"
  | "blocked"
  | "done";

export type ProjectPhase =
  | "idle"
  | "planning"
  | "waiting_plan_review"
  | "offline_prep"
  | "building_ui"
  | "seeding"
  | "qa_testing"
  | "waiting_bug_review"
  | "fixing"
  | "re_testing"
  | "completed"
  | "failed";

export type AgentLocation = "desk" | "leader_desk" | "bug_board" | "lounge";
export type ExecutionKind = "offline" | "ai" | "idle";

export interface ToolCallLog {
  name: string;
  args?: Record<string, unknown> | string;
  kind?: string;
  timestamp?: string;
}

export interface ChatMessage {
  sender: "user" | "agent" | "system";
  text: string;
  timestamp?: string;
}

export interface AgentState {
  id: string;
  name: string;
  role: AgentRole;
  title: string;
  status: AgentVisualStatus;
  location: AgentLocation;
  current_task: string;
  bubble_text: string;
  execution_kind: ExecutionKind;
  edited_files: string[];
  thoughts: string[];
  tool_calls: ToolCallLog[];
  chat_history: ChatMessage[];
}

export interface TaskItem {
  id: string;
  title: string;
  owner_role: AgentRole;
  status: "pending" | "in_progress" | "done" | "failed";
  execution_kind: ExecutionKind;
  detail: string;
  output_files: string[];
}

export interface BugItem {
  id: string;
  title: string;
  description: string;
  severity: "critical" | "major" | "minor";
  source: "offline_static" | "offline_playwright" | "ai_vision";
  viewport: "desktop" | "tablet" | "mobile" | "all";
  file_path: string;
  selector_or_rule: string;
  screenshot_url?: string | null;
  assigned_role: AgentRole;
  status: "pending_review" | "approved_for_fix" | "ignored" | "fixed" | "still_failing";
  user_note: string;
  qa_round: number;
}

export interface BugDecisionItem {
  bug_id: string;
  action: "fix" | "ignore";
  user_note: string;
}

export interface BugReviewRequest {
  decisions: BugDecisionItem[];
  action_mode: "fix_selected" | "skip_and_complete";
}

export interface PlanTaskUpdate {
  id: string;
  title: string;
  detail: string;
}

export type SpecContentType =
  | "product"
  | "article_single"
  | "article_list"
  | "album"
  | "video"
  | "form"
  | "layout"
  | "feature";

export type SpecSectionScope = "menu" | "homepage" | "inner_page" | "global";
export type SpecSectionSource = "figma_and_spec" | "figma_only" | "spec_only";
export type SpecCardinality = "single" | "multiple" | "none";

export interface SpecSectionItem {
  id: string;
  order: number;
  name: string;
  scope: SpecSectionScope;
  source: SpecSectionSource;
  figma_section_name: string;
  content_type: SpecContentType;
  category_levels: number;
  item_cardinality: SpecCardinality;
  spec_requirements: string;
  notes: string;
}

export interface PlanApprovalRequest {
  leader_plan_markdown: string;
  spec_sections?: SpecSectionItem[];
  spec_global_features?: string[];
  tasks?: PlanTaskUpdate[];
  user_note: string;
}

export interface TokenStats {
  offline_steps_completed: number;
  ai_calls_made: number;
  raw_figma_nodes: number;
  kept_figma_nodes: number;
  estimated_tokens_saved_pct: number;
}

export interface ProjectState {
  id: string;
  name: string;
  spec_text: string;
  figma_url: string;
  target_source_dir: string;
  framework: string;
  mode: "demo" | "live_sdk";
  enable_ai_vision_qa: boolean;
  phase: ProjectPhase;
  qa_round: number;
  leader_plan_markdown: string;
  spec_sections?: SpecSectionItem[];
  spec_metadata?: Record<string, string>;
  spec_global_features?: string[];
  missing_fonts?: string[];
  plan_approved: boolean;
  plan_review_note: string;
  token_stats: TokenStats;
  figma_summary: Record<string, unknown>;
  tokens_json_url?: string | null;
  preview_url?: string | null;
  screenshots: Record<string, string>;
  agents: Record<string, AgentState>;
  tasks: TaskItem[];
  bugs: BugItem[];
  timeline: Array<{ timestamp?: string; actor?: string; text: string; kind?: string }>;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthInfo {
  ok: boolean;
  sdk: { available: boolean; detail: string };
  figma_token_configured?: boolean;
  playwright_ready: boolean;
  default_source_dir: string;
}

export interface ProjectCreatePayload {
  name: string;
  spec_text: string;
  figma_url: string;
  figma_token?: string;
  target_source_dir: string;
  preview_url?: string;
  mode: "demo" | "live_sdk";
  enable_ai_vision_qa: boolean;
}
