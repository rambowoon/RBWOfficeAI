from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

AgentRole = Literal[
    "leader",
    "dev",
    "config",
    "asset",
    "ui_dev_1",
    "ui_dev_2",
    "seeder",
    "qa",
]

AgentVisualStatus = Literal[
    "idle",
    "walking",
    "working_offline",
    "working_ai",
    "meeting_leader",
    "waiting_review",
    "blocked",
    "done",
]

ProjectPhase = Literal[
    "idle",
    "planning",
    "waiting_plan_review",
    "offline_prep",
    "building_ui",
    "seeding",
    "qa_testing",
    "waiting_bug_review",
    "fixing",
    "re_testing",
    "completed",
    "failed",
]

AgentLocation = Literal["desk", "leader_desk", "bug_board", "lounge"]
ExecutionKind = Literal["offline", "ai", "idle"]

SpecContentType = Literal[
    "product",
    "article_single",
    "article_list",
    "album",
    "video",
    "form",
    "layout",
    "feature",
]
SpecSectionScope = Literal["menu", "homepage", "inner_page", "global"]
SpecSectionSource = Literal["figma_and_spec", "figma_only", "spec_only"]
SpecCardinality = Literal["single", "multiple", "none"]


class SpecSectionItem(BaseModel):
    id: str
    order: int = 1
    name: str
    scope: SpecSectionScope = "homepage"
    source: SpecSectionSource = "figma_and_spec"
    figma_section_name: str = ""
    content_type: SpecContentType = "layout"
    category_levels: int = Field(default=0, ge=0, le=3)
    item_cardinality: SpecCardinality = "none"
    spec_requirements: str = ""
    notes: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectCreate(BaseModel):
    name: str = Field(default="", max_length=120)
    spec_text: str = Field(..., min_length=1)
    figma_url: str = Field(default="")
    figma_token: Optional[str] = Field(default=None)
    target_source_dir: str = Field(default="")
    preview_url: Optional[str] = Field(default=None)
    mode: Literal["demo", "live_sdk"] = "demo"
    enable_ai_vision_qa: bool = False


class AgentState(BaseModel):
    id: str
    name: str
    role: AgentRole
    title: str
    status: AgentVisualStatus = "idle"
    location: AgentLocation = "desk"
    current_task: str = ""
    bubble_text: str = ""
    execution_kind: ExecutionKind = "idle"
    edited_files: list[str] = Field(default_factory=list)
    thoughts: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    chat_history: list[dict[str, str]] = Field(default_factory=list)


class TaskItem(BaseModel):
    id: str
    title: str
    owner_role: AgentRole
    status: Literal["pending", "in_progress", "done", "failed"] = "pending"
    execution_kind: ExecutionKind = "offline"
    detail: str = ""
    output_files: list[str] = Field(default_factory=list)


class BugItem(BaseModel):
    id: str
    title: str
    description: str
    severity: Literal["critical", "major", "minor"] = "major"
    source: Literal["offline_static", "offline_playwright", "ai_vision"] = "offline_playwright"
    viewport: Literal["desktop", "tablet", "mobile", "all"] = "all"
    file_path: str = ""
    selector_or_rule: str = ""
    screenshot_url: Optional[str] = None
    assigned_role: AgentRole = "dev"
    status: Literal[
        "pending_review",
        "approved_for_fix",
        "ignored",
        "fixed",
        "still_failing",
    ] = "pending_review"
    user_note: str = ""
    qa_round: int = 1


class BugDecisionItem(BaseModel):
    bug_id: str
    action: Literal["fix", "ignore"]
    user_note: str = ""


class BugReviewRequest(BaseModel):
    decisions: list[BugDecisionItem] = Field(default_factory=list)
    action_mode: Literal["fix_selected", "skip_and_complete"] = "fix_selected"


class PlanTaskUpdate(BaseModel):
    id: str
    title: str = Field(..., min_length=1)
    detail: str = ""


class PlanApprovalRequest(BaseModel):
    leader_plan_markdown: str = Field(default="")
    spec_sections: Optional[list[SpecSectionItem]] = None
    spec_global_features: Optional[list[str]] = None
    tasks: Optional[list[PlanTaskUpdate]] = None
    user_note: str = ""


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class TokenStats(BaseModel):
    offline_steps_completed: int = 0
    ai_calls_made: int = 0
    raw_figma_nodes: int = 0
    kept_figma_nodes: int = 0
    estimated_tokens_saved_pct: int = 0


class ProjectState(BaseModel):
    id: str
    name: str
    spec_text: str
    figma_url: str = ""
    target_source_dir: str = ""
    framework: str = "generic"
    mode: Literal["demo", "live_sdk"] = "demo"
    enable_ai_vision_qa: bool = False
    phase: ProjectPhase = "idle"
    qa_round: int = 0
    leader_plan_markdown: str = ""
    spec_sections: list[SpecSectionItem] = Field(default_factory=list)
    spec_metadata: dict[str, str] = Field(default_factory=dict)
    spec_global_features: list[str] = Field(default_factory=list)
    missing_fonts: list[str] = Field(default_factory=list)
    plan_approved: bool = False
    plan_review_note: str = ""
    token_stats: TokenStats = Field(default_factory=TokenStats)
    figma_summary: dict[str, Any] = Field(default_factory=dict)
    tokens_json_url: Optional[str] = None
    preview_url: Optional[str] = None
    screenshots: dict[str, str] = Field(default_factory=dict)
    agents: dict[str, AgentState] = Field(default_factory=dict)
    tasks: list[TaskItem] = Field(default_factory=list)
    bugs: list[BugItem] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


def build_default_agents() -> dict[str, AgentState]:
    specs: list[tuple[str, str, AgentRole, str]] = [
        ("leader", "Thiện (Leader)", "leader", "Tech Lead & Architect"),
        ("asset", "Linh (Assets & Config)", "asset", "Config, Font/WebP & Seed"),
        ("dev", "Vy (UI & Frontend)", "dev", "HTML/Blade, CSS & Responsive"),
        ("qa", "Tuấn (QA & Tester)", "qa", "Static & Playwright QA"),
    ]
    return {
        agent_id: AgentState(
            id=agent_id,
            name=name,
            role=role,
            title=title,
            status="idle",
            location="leader_desk" if role == "leader" else "desk",
        )
        for agent_id, name, role, title in specs
    }
