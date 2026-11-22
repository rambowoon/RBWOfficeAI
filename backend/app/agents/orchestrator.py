from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from ..config import ARTIFACTS_DIR, PROJECTS_DIR, settings
from ..event_bus import EventBus
from ..models import (
    AgentLocation,
    AgentRole,
    AgentState,
    AgentVisualStatus,
    BugItem,
    BugReviewRequest,
    ExecutionKind,
    PlanApprovalRequest,
    ProjectCreate,
    ProjectPhase,
    ProjectState,
    TaskItem,
    build_default_agents,
    utc_now_iso,
)
from ..offline.asset_pipeline import run_asset_and_font_pipeline
from ..offline.figma_parser import fetch_figma_tokens, parse_figma_url
from ..offline.qa_runner import run_playwright_checks, run_static_checks
from ..offline.source_scaffold import (
    apply_demo_bug_fixes,
    build_demo_preview_site,
    generate_demo_seed_data,
    inspect_workspace_context,
)
from .prompts import build_agent_system_instructions
from .sdk_adapter import AntigravityAgentRunner


class OfficeOrchestrator:
    """Coordinates Offline 0-token engines, Antigravity SDK agents, and the 3D Bug Review gate."""

    def __init__(
        self, bus: EventBus, step_delay: float = 0.55, walk_delay: float = 2.6
    ) -> None:
        self.bus = bus
        self.step_delay = step_delay
        self.walk_delay = walk_delay
        self.sdk_runner = AntigravityAgentRunner()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._ephemeral_figma_tokens: dict[str, str] = {}
        self._ephemeral_assets: dict[str, dict[str, Any]] = {}
        self._ephemeral_tokens_data: dict[str, dict[str, Any]] = {}
        self._ephemeral_workspace: dict[str, dict[str, Any]] = {}

    async def create_and_start(self, req: ProjectCreate) -> ProjectState:
        project_id = uuid.uuid4().hex[:10]
        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (ARTIFACTS_DIR / project_id).mkdir(parents=True, exist_ok=True)

        workspace_ctx = inspect_workspace_context(req.target_source_dir)
        self._ephemeral_workspace[project_id] = workspace_ctx

        token = (req.figma_token or settings.FIGMA_ACCESS_TOKEN or "").strip()
        if token:
            self._ephemeral_figma_tokens[project_id] = token

        state = ProjectState(
            id=project_id,
            name=req.name,
            spec_text=req.spec_text,
            figma_url=req.figma_url,
            target_source_dir=req.target_source_dir,
            framework=workspace_ctx["framework"],
            mode=req.mode,
            enable_ai_vision_qa=req.enable_ai_vision_qa,
            phase="planning",
            preview_url=req.preview_url or f"/preview-sandbox/{project_id}/preview_site/index.html",
            agents=build_default_agents(),
        )
        self.bus.save_project(state)
        await self.bus.emit_project_sync(state, "project_created")

        task = asyncio.create_task(self._run_leader_analysis(project_id))
        self._tasks[project_id] = task
        return state

    async def _log_timeline(
        self, state: ProjectState, actor: str, text: str, kind: str = "info"
    ) -> None:
        state.timeline.append(
            {
                "timestamp": utc_now_iso(),
                "actor": actor,
                "text": text,
                "kind": kind,
            }
        )
        if len(state.timeline) > 80:
            state.timeline = state.timeline[-80:]

    async def _update_agent(
        self,
        state: ProjectState,
        agent_id: str,
        *,
        status: AgentVisualStatus | None = None,
        location: AgentLocation | None = None,
        current_task: str | None = None,
        bubble_text: str | None = None,
        execution_kind: ExecutionKind | None = None,
        thought: str | None = None,
        tool_call: dict[str, Any] | None = None,
        edited_file: str | None = None,
    ) -> None:
        agent: AgentState = state.agents[agent_id]
        if status is not None:
            agent.status = status
        if location is not None:
            agent.location = location
        if current_task is not None:
            agent.current_task = current_task
        if bubble_text is not None:
            agent.bubble_text = bubble_text
        if execution_kind is not None:
            agent.execution_kind = execution_kind
        if thought:
            agent.thoughts.append(thought)
            agent.thoughts = agent.thoughts[-30:]
        if tool_call:
            agent.tool_calls.append(tool_call)
            agent.tool_calls = agent.tool_calls[-30:]
        if edited_file and edited_file not in agent.edited_files:
            agent.edited_files.append(edited_file)

        await self.bus.emit(
            "agent_update",
            state.id,
            {"agent": agent.model_dump(mode="json")},
            persist_state=state,
        )

    async def _set_phase(self, state: ProjectState, phase: ProjectPhase) -> None:
        state.phase = phase
        await self.bus.emit_project_sync(state, f"phase_{phase}")

    async def _walk_to(
        self, state: ProjectState, agent_id: str, target: AgentLocation, bubble: str
    ) -> None:
        await self._update_agent(
            state,
            agent_id,
            status="walking",
            location=target,
            bubble_text=bubble,
        )
        await asyncio.sleep(self.walk_delay)

    async def _brief_at_leader(
        self, state: ProjectState, agent_id: str, task_title: str
    ) -> None:
        """Have an employee walk to Leader's room, get briefed, and return to their own desk."""
        agent_name = state.agents[agent_id].name
        await self._walk_to(state, agent_id, "leader_desk", "🚶 Chạy qua phòng Leader nhận việc...")
        await self._update_agent(
            state,
            "leader",
            status="meeting_leader",
            bubble_text=f"📋 Giao việc cho {agent_name}",
        )
        await self._update_agent(
            state,
            agent_id,
            status="meeting_leader",
            location="leader_desk",
            current_task=task_title,
            bubble_text="👂 Đang nghe Leader giao việc...",
        )
        await asyncio.sleep(self.step_delay)
        await self._update_agent(
            state,
            "leader",
            status="idle",
            bubble_text="👀 Theo dõi tiến độ team",
        )
        await self._walk_to(state, agent_id, "desk", "🚶 Chạy về bàn làm việc...")

    async def _handoff_to_leader_and_relax(
        self, state: ProjectState, agent_id: str, handoff_msg: str
    ) -> None:
        """After finishing work, hand results back to Leader and head to the Entertainment Lounge."""
        agent_name = state.agents[agent_id].name
        await self._walk_to(state, agent_id, "leader_desk", "🚶 Chạy qua trả bài cho Leader...")
        await self._update_agent(
            state,
            "leader",
            status="meeting_leader",
            bubble_text=f"✅ Nhận bài từ {agent_name}",
        )
        await self._update_agent(
            state,
            agent_id,
            status="meeting_leader",
            location="leader_desk",
            bubble_text=f"📦 {handoff_msg}",
        )
        await asyncio.sleep(self.step_delay)
        await self._update_agent(
            state,
            "leader",
            status="idle",
            bubble_text="👀 Sẵn sàng giao việc tiếp theo",
        )
        await self._walk_to(state, agent_id, "lounge", "🚶 Xong việc! Ra phòng giải trí nghỉ...")
        await self._update_agent(
            state,
            agent_id,
            status="done",
            location="lounge",
            bubble_text="☕ Nghỉ ngơi ở phòng giải trí",
        )

    def _recompute_token_stats(self, state: ProjectState, tokens_data: dict[str, Any] | None = None) -> None:
        if tokens_data:
            stats = tokens_data.get("stats") or {}
            state.token_stats.raw_figma_nodes = int(stats.get("raw_node_count", 0))
            state.token_stats.kept_figma_nodes = int(stats.get("kept_node_count", 0))
        off = state.token_stats.offline_steps_completed
        ai = state.token_stats.ai_calls_made
        total = off + ai
        state.token_stats.estimated_tokens_saved_pct = (
            round((off / total) * 100) if total > 0 else 0
        )

    def _resolve_local_qa_url(self, state: ProjectState) -> str:
        """Convert relative sandbox URL into local loopback URL so Playwright can visit it."""
        if state.preview_url and state.preview_url.startswith(("http://", "https://")):
            return state.preview_url
        rel = state.preview_url or f"/preview-sandbox/{state.id}/preview_site/index.html"
        if not rel.startswith("/"):
            rel = f"/{rel}"
        return f"http://{settings.HOST}:{settings.PORT}{rel}"

    async def _run_sdk_with_fallback(
        self,
        state: ProjectState,
        agent_id: str,
        prompt: str,
        working_dir: str | None = None,
    ) -> str:
        workspace_ctx = self._ephemeral_workspace.get(state.id) or inspect_workspace_context(
            state.target_source_dir
        )
        sys_inst = build_agent_system_instructions(agent_id, workspace_ctx)
        skills_dir = str(Path(state.target_source_dir) / ".agents" / "skills")

        state.token_stats.ai_calls_made += 1
        self._recompute_token_stats(state)

        async def _on_thought(txt: str) -> None:
            await self._update_agent(state, agent_id, thought=txt[:280])

        async def _on_tool(call: dict[str, Any]) -> None:
            await self._update_agent(
                state,
                agent_id,
                bubble_text=f"🤖 {call['name']}",
                tool_call=call,
            )

        return await self.sdk_runner.run_task(
            system_instructions=sys_inst,
            prompt=prompt,
            working_dir=working_dir,
            skills_dir=skills_dir,
            on_thought=_on_thought,
            on_tool_call=_on_tool,
        )

    def _build_default_leader_plan_markdown(
        self,
        state: ProjectState,
        tokens_data: dict[str, Any],
        workspace_ctx: dict[str, Any],
    ) -> str:
        stats = tokens_data.get("stats") or {}
        colors = tokens_data.get("colors") or []
        color_list = ", ".join(
            f"{c.get('name', 'Color')} ({c.get('hex', '')})" for c in colors[:6]
        ) or "#1d4ed8, #0f766e"
        fonts = ", ".join(tokens_data.get("fonts") or ["Be Vietnam Pro"])
        sections = tokens_data.get("sections") or []
        section_lines = "\n".join(
            f"  {idx + 1}. **{sec.get('name', f'Section {idx + 1}')}**"
            + (f" — {sec.get('role')}" if sec.get("role") else "")
            for idx, sec in enumerate(sections)
        ) or "  1. Header, Hero Banner, Danh mục nổi bật, Giới thiệu & Footer Form"

        nasanic_rule = (
            "Tuân thủ CSS Nasanic (CẤM dùng `aspect-ratio`, tách rõ `fonts.css` / `style.css` / `media.css`)"
            if workspace_ctx.get("framework") == "nasanic"
            else "Tuân thủ HTML5 semantic & Vanilla CSS sạch"
        )
        return (
            f"# ĐẶC TẢ PHÂN TÍCH DỰ ÁN: {state.name}\n\n"
            f"## 1. Nguồn thiết kế & Môi trường\n"
            f"- Figma File: {tokens_data.get('file_name') or 'Demo Design System'} "
            f"(Nén {stats.get('compression_pct', 0)}% node rác: {stats.get('kept_node_count', 0)}/{stats.get('raw_node_count', 0)} nodes)\n"
            f"- Framework phát hiện: `{workspace_ctx.get('framework', 'generic')}`\n"
            f"- Bảng màu Tokens: {color_list}\n"
            f"- Typography: {fonts}\n\n"
            f"## 2. Cấu trúc Section trích xuất từ Figma\n"
            f"{section_lines}\n\n"
            f"## 3. Yêu cầu chi tiết từ Đặc tả gốc\n"
            f"{state.spec_text.strip()}\n\n"
            f"## 4. Ràng buộc kỹ thuật & Responsive\n"
            f"- {nasanic_rule}\n"
            f"- Tối ưu toàn bộ hình ảnh sang `.webp` + SVG icon sắc nét.\n"
            f"- Responsive chuẩn 3 màn hình kiểm thử: Desktop `1440px`, Tablet `768px`, Mobile `375px` (không tràn ngang).\n\n"
            f"## 5. Kế hoạch triển khai 3 nhân viên\n"
            f"- **Linh (`asset`)**: Cấu hình source `{workspace_ctx.get('framework', 'generic')}`, sinh `fonts.css`, nén ảnh WebP & tạo `seed.json` tiếng Việt.\n"
            f"- **Vy (`dev`)**: Code HTML/Blade, Vanilla CSS, JS & responsive theo đúng đặc tả đã duyệt.\n"
            f"- **Tuấn (`qa`)**: Chạy Static Lint + Playwright 3 viewports để bắt lỗi và đưa lên Bug Board."
        )

    async def _run_leader_analysis(self, project_id: str) -> None:
        state = self.bus.get_project(project_id)
        if not state:
            return

        project_dir = PROJECTS_DIR / project_id
        figma_token = self._ephemeral_figma_tokens.get(project_id)
        workspace_ctx = self._ephemeral_workspace.get(project_id) or inspect_workspace_context(
            state.target_source_dir
        )

        try:
            # ------------------------------------------------------------------
            # GATE 1: LEADER ANALYZES FIGMA + SPEC, THEN PAUSES FOR USER APPROVAL
            # ------------------------------------------------------------------
            await self._set_phase(state, "planning")
            await self._update_agent(
                state,
                "leader",
                status="working_offline",
                location="leader_desk",
                execution_kind="offline",
                current_task="Lọc Figma JSON & tạo tokens.json (0 token)",
                bubble_text="⚡ 0-token: Đọc & lọc rác Figma...",
                thought="Gọi Offline Figma Parser bỏ layer ẩn và gom màu/font thành tokens.json.",
                tool_call={
                    "name": "offline_figma_parser",
                    "args": {"figma_url": state.figma_url or "demo"},
                    "kind": "offline_script",
                    "timestamp": utc_now_iso(),
                },
            )
            tokens_data = await fetch_figma_tokens(
                state.figma_url, figma_token, state.mode, state.spec_text
            )
            self._ephemeral_tokens_data[project_id] = tokens_data
            tokens_file = project_dir / "tokens.json"
            tokens_file.write_text(
                json.dumps(tokens_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            state.tokens_json_url = f"/api/projects/{project_id}/tokens"
            state.figma_summary = {
                "file_name": tokens_data.get("file_name"),
                "colors_count": len(tokens_data.get("colors", [])),
                "fonts": tokens_data.get("fonts", []),
                "sections_count": len(tokens_data.get("sections", [])),
                "stats": tokens_data.get("stats", {}),
            }
            state.token_stats.offline_steps_completed += 1
            self._recompute_token_stats(state, tokens_data)
            await self._log_timeline(
                state,
                "Minh (Leader)",
                f"Đã trích xuất tokens.json offline (nén {tokens_data.get('stats', {}).get('compression_pct', 0)}% node rác, 0 token).",
                "offline",
            )

            await self._update_agent(
                state,
                "leader",
                status="working_ai",
                execution_kind="ai",
                current_task="Phân tích đặc tả & lập kế hoạch trình bạn duyệt",
                bubble_text="🤖 AI: Soạn bản phân tích đặc tả...",
                edited_file="tokens.json",
            )

            default_plan = self._build_default_leader_plan_markdown(
                state, tokens_data, workspace_ctx
            )
            if state.mode == "live_sdk":
                plan_prompt = (
                    f"Phân tích đặc tả gốc và Figma tokens bên dưới, xuất ra bản ĐẶC TẢ KỸ THUẬT CHI TIẾT bằng tiếng Việt (Markdown) "
                    f"để người dùng xem, chỉnh sửa và duyệt trước khi giao cho 3 nhân viên: Linh (Assets/Config/Seed), Vy (UI/Frontend), Tuấn (QA).\n"
                    f"Framework phát hiện: {workspace_ctx['framework']}\n"
                    f"Đặc tả gốc:\n{state.spec_text}\n\n"
                    f"Figma Tokens:\n{json.dumps(tokens_data, ensure_ascii=False)[:3200]}"
                )
                try:
                    leader_reply = await self._run_sdk_with_fallback(
                        state, "leader", plan_prompt, state.target_source_dir
                    )
                    state.leader_plan_markdown = (
                        leader_reply.strip() if len(leader_reply.strip()) >= 40 else default_plan
                    )
                    await self._update_agent(
                        state,
                        "leader",
                        thought=f"Đã phân tích đặc tả qua AI SDK ({len(state.leader_plan_markdown)} ký tự). Chờ bạn duyệt.",
                    )
                except Exception as sdk_exc:
                    await self._handle_sdk_error(state, "leader", sdk_exc)
                    return
            else:
                state.token_stats.ai_calls_made += 1
                self._recompute_token_stats(state)
                await asyncio.sleep(self.step_delay)
                state.leader_plan_markdown = default_plan
                await self._update_agent(
                    state,
                    "leader",
                    thought=(
                        f"Đã map {len(tokens_data.get('sections', []))} section Figma với đặc tả "
                        f"và soạn xong bản phân tích `leader_plan.md`. Đang chờ bạn xem/sửa trước khi giao cho Linh, Vy, Tuấn."
                    ),
                )

            plan_file = project_dir / "leader_plan.md"
            plan_file.write_text(state.leader_plan_markdown, encoding="utf-8")

            state.tasks = [
                TaskItem(
                    id="t-asset",
                    title="Cấu hình workspace, nén WebP/Font & sinh dữ liệu mẫu",
                    owner_role="asset",
                    execution_kind="offline",
                    detail=f"Quét rules `{workspace_ctx['framework']}`, sinh fonts.css, nén ảnh WebP & tạo data/seed.json.",
                ),
                TaskItem(
                    id="t-dev",
                    title="Code HTML/Blade, Vanilla CSS, JS & Responsive",
                    owner_role="dev",
                    execution_kind="ai",
                    detail="Dựng layout theo đúng đặc tả phân tích đã duyệt, đảm bảo Desktop 1440 / Tablet 768 / Mobile 375.",
                ),
                TaskItem(
                    id="t-qa",
                    title="Pre-QA Offline (Static Lint + Playwright 3 viewports)",
                    owner_role="qa",
                    execution_kind="offline",
                    detail="Kiểm tra CSS/JS/PHP lint + chụp Playwright 3 kích thước màn hình và treo Bug Board.",
                ),
            ]
            state.plan_approved = False

            await self._update_agent(
                state,
                "leader",
                status="waiting_review",
                location="leader_desk",
                current_task="Chờ bạn xem, chỉnh sửa & duyệt đặc tả phân tích",
                bubble_text="🟡 Chờ bạn duyệt đặc tả!",
                edited_file="leader_plan.md",
            )
            for staff_id in ("asset", "dev", "qa"):
                if staff_id in state.agents:
                    await self._update_agent(
                        state,
                        staff_id,
                        status="idle",
                        location="desk",
                        bubble_text="⏳ Chờ Leader chốt đặc tả...",
                    )
            await self._log_timeline(
                state,
                "Minh (Leader)",
                "Đã phân tích xong đặc tả & chia 3 đầu việc dự kiến. Đang chờ bạn xem, chỉnh sửa và bấm Duyệt để giao xuống nhân viên.",
                "warning",
            )
            await self._set_phase(state, "waiting_plan_review")

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.phase = "failed"
            state.error_message = str(exc)
            await self._log_timeline(state, "System", f"Lỗi phân tích Leader: {exc}", "error")
            await self.bus.emit_project_sync(state, "pipeline_failed")

    async def approve_leader_plan(
        self, project_id: str, req: PlanApprovalRequest
    ) -> ProjectState:
        state = self.bus.get_project(project_id)
        if not state:
            raise KeyError("Project not found")
        if state.phase != "waiting_plan_review" or state.plan_approved:
            raise ValueError(
                f"Project is in phase '{state.phase}', not 'waiting_plan_review'"
            )

        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        state.leader_plan_markdown = req.leader_plan_markdown.strip()
        (project_dir / "leader_plan.md").write_text(
            state.leader_plan_markdown, encoding="utf-8"
        )

        if req.tasks:
            updates_by_id = {t.id: t for t in req.tasks}
            for task_item in state.tasks:
                upd = updates_by_id.get(task_item.id)
                if upd:
                    task_item.title = upd.title.strip()
                    task_item.detail = upd.detail.strip()

        state.plan_approved = True
        state.plan_review_note = req.user_note.strip()

        await self._update_agent(
            state,
            "leader",
            status="meeting_leader",
            location="leader_desk",
            current_task="Giao đặc tả đã duyệt xuống team thực thi",
            bubble_text="✅ Đặc tả đã duyệt! Giao việc cho Linh...",
            thought="Người dùng đã duyệt đặc tả phân tích. Bắt đầu giao lần lượt cho Linh → Vy → Tuấn.",
        )
        await self._log_timeline(
            state,
            "Bạn (Reviewer)",
            "Đã duyệt đặc tả phân tích của Leader. Bắt đầu giao xuống nhân viên triển khai!",
            "success",
        )
        await self._set_phase(state, "offline_prep")

        task = asyncio.create_task(self._run_staff_execution(project_id))
        self._tasks[project_id] = task
        return state

    async def _run_staff_execution(self, project_id: str) -> None:
        state = self.bus.get_project(project_id)
        if not state:
            return

        project_dir = PROJECTS_DIR / project_id
        preview_dir = project_dir / "preview_site"
        figma_token = self._ephemeral_figma_tokens.get(project_id)
        workspace_ctx = self._ephemeral_workspace.get(project_id) or inspect_workspace_context(
            state.target_source_dir
        )

        tokens_data = self._ephemeral_tokens_data.get(project_id)
        if not tokens_data:
            tokens_file = project_dir / "tokens.json"
            if tokens_file.exists():
                tokens_data = json.loads(tokens_file.read_text(encoding="utf-8"))
            else:
                tokens_data = await fetch_figma_tokens(
                    state.figma_url, figma_token, state.mode, state.spec_text
                )
            self._ephemeral_tokens_data[project_id] = tokens_data

        approved_spec = state.leader_plan_markdown.strip() or state.spec_text
        if state.plan_review_note:
            approved_spec = (
                f"{approved_spec}\n\n=== GHI CHÚ DUYỆT TỪ NGƯỜI DÙNG ===\n{state.plan_review_note}"
            )

        try:
            # ------------------------------------------------------------------
            # PHASE 2 & 3: NV 1 (LINH - ASSET/CONFIG/SEED) -> HANDOFF -> LOUNGE
            # ------------------------------------------------------------------
            await self._set_phase(state, "offline_prep")
            await self._brief_at_leader(state, "asset", state.tasks[0].title)
            state.tasks[0].status = "in_progress"
            await self._update_agent(
                state,
                "asset",
                status="working_offline",
                execution_kind="offline",
                current_task="Quét source, cài font & nén ảnh WebP (0 token)",
                bubble_text=f"⚡ 0-token: Quét {workspace_ctx['framework']} + nén WebP...",
                tool_call={
                    "name": "run_asset_and_font_pipeline",
                    "args": {
                        "framework": workspace_ctx["framework"],
                        "fonts": tokens_data.get("fonts", []),
                    },
                    "kind": "offline_script",
                    "timestamp": utc_now_iso(),
                },
            )

            file_key, _ = parse_figma_url(state.figma_url)
            assets_manifest = await run_asset_and_font_pipeline(
                tokens_data,
                preview_dir,
                figma_file_key=file_key,
                figma_token=figma_token,
            )
            self._ephemeral_assets[project_id] = assets_manifest
            state.token_stats.offline_steps_completed += 2
            self._recompute_token_stats(state)
            await asyncio.sleep(self.step_delay)

            state.tasks[0].output_files = [
                assets_manifest["fonts_css"],
                *assets_manifest.get("images", []),
                *assets_manifest.get("icons", []),
            ]
            await self._set_phase(state, "seeding")
            seed_data = generate_demo_seed_data(state.name, approved_spec, tokens_data)
            data_dir = preview_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "seed.json").write_text(
                json.dumps(seed_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            state.tasks[0].output_files = [*state.tasks[0].output_files, "data/seed.json"]
            state.token_stats.offline_steps_completed += 1
            self._recompute_token_stats(state)
            await self._update_agent(
                state,
                "asset",
                status="working_offline",
                bubble_text="⚡ Sinh seed.json & hoàn tất Config...",
                edited_file="assets/css/fonts.css",
                thought=(
                    f"Phát hiện `{workspace_ctx['framework']}`. Đã sinh `fonts.css`, "
                    f"{len(assets_manifest.get('images', []))} ảnh WebP và seed data theo đặc tả đã duyệt (0 token)."
                ),
            )
            await self._update_agent(state, "asset", edited_file="data/seed.json")
            await asyncio.sleep(self.step_delay)
            state.tasks[0].status = "done"
            await self._log_timeline(
                state,
                "Linh (Assets & Config)",
                f"Đã cấu hình source, tạo fonts.css, {len(assets_manifest.get('images', []))} WebP & seed.json (0 token) rồi ra phòng giải trí.",
                "offline",
            )
            await self._handoff_to_leader_and_relax(
                state, "asset", "Xong Config, WebP/Font & Seed"
            )

            # ------------------------------------------------------------------
            # PHASE 4: NV 2 (VY - UI & FRONTEND) -> HANDOFF -> LOUNGE
            # ------------------------------------------------------------------
            await self._set_phase(state, "building_ui")
            await self._brief_at_leader(state, "dev", state.tasks[1].title)
            state.tasks[1].status = "in_progress"
            await self._update_agent(
                state,
                "dev",
                status="working_ai",
                execution_kind="ai",
                current_task=state.tasks[1].title,
                bubble_text="🤖 AI: Code HTML/Blade, Vanilla CSS & Responsive...",
                edited_file="index.html",
            )

            if state.mode == "live_sdk":
                dev_prompt = (
                    f"Triển khai giao diện HTML/Blade, Vanilla CSS (`assets/css/style.css`, `assets/css/media.css`) "
                    f"và JS (`assets/js/apps.js`) chuẩn dự án {workspace_ctx['framework']}.\n"
                    f"ĐẶC TẢ ĐÃ DUYỆT:\n{approved_spec}\n\n"
                    f"Tài nguyên Linh đã tạo sẵn trong `{preview_dir}`:\n"
                    f"- Font CSS: `{assets_manifest['fonts_css']}` (Fonts: {', '.join(tokens_data.get('fonts', []))})\n"
                    f"- Ảnh WebP: {', '.join(assets_manifest.get('images', []))}\n"
                    f"- Icons SVG: {', '.join(assets_manifest.get('icons', []))}\n"
                    f"- Seed data: `{preview_dir / 'data' / 'seed.json'}`\n"
                    f"Source gốc: `{state.target_source_dir}`.\n"
                    f"Tokens màu: {json.dumps(tokens_data.get('colors', [])[:6], ensure_ascii=False)}\n"
                    f"Đảm bảo breakpoint 1199/992/767/575/400 và không tràn ngang."
                )
                try:
                    await self._run_sdk_with_fallback(
                        state, "dev", dev_prompt, state.target_source_dir
                    )
                except Exception as sdk_exc:
                    await self._handle_sdk_error(state, "dev", sdk_exc)
                    return

                if not (preview_dir / "index.html").exists():
                    build_demo_preview_site(
                        project_dir,
                        state.name,
                        approved_spec,
                        tokens_data,
                        assets_manifest,
                        seed_data,
                        inject_round1_bugs=False,
                    )
            else:
                state.token_stats.ai_calls_made += 1
                self._recompute_token_stats(state)
                build_demo_preview_site(
                    project_dir,
                    state.name,
                    approved_spec,
                    tokens_data,
                    assets_manifest,
                    seed_data,
                    inject_round1_bugs=True,
                )
                await asyncio.sleep(self.step_delay)

            state.tasks[1].status = "done"
            await self._update_agent(
                state,
                "dev",
                status="done",
                bubble_text="✅ Xong HTML, CSS & Responsive",
                edited_file="assets/css/media.css",
            )
            await self._log_timeline(
                state,
                "Vy (UI & Frontend)",
                "Đã hoàn thiện HTML, Vanilla CSS & Responsive theo đặc tả đã duyệt, trả bài Leader và ra phòng giải trí.",
                "ai",
            )
            await self._handoff_to_leader_and_relax(
                state, "dev", "Xong HTML, CSS & Responsive"
            )

            # ------------------------------------------------------------------
            # PHASE 5: OFFLINE PRE-QA (STATIC + REAL PLAYWRIGHT — 0 TOKEN)
            # ------------------------------------------------------------------
            await self._run_qa_pass(state, qa_round=1, ignored_bug_ids=set())

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.phase = "failed"
            state.error_message = str(exc)
            await self._log_timeline(state, "System", f"Lỗi pipeline: {exc}", "error")
            await self.bus.emit_project_sync(state, "pipeline_failed")

    async def _run_qa_pass(
        self,
        state: ProjectState,
        *,
        qa_round: int,
        ignored_bug_ids: set[str],
    ) -> None:
        state.qa_round = qa_round
        await self._set_phase(state, "qa_testing" if qa_round == 1 else "re_testing")

        if qa_round == 1:
            qa_task = next((t for t in state.tasks if t.owner_role == "qa"), None)
            await self._brief_at_leader(
                state,
                "qa",
                qa_task.title if qa_task else "Pre-QA Offline (Static Lint + Playwright 3 viewports)",
            )
        else:
            await self._walk_to(state, "qa", "desk", "🚶 Về bàn chạy QA kiểm tra lại...")
        await self._update_agent(
            state,
            "qa",
            status="working_offline",
            execution_kind="offline",
            current_task=f"Kiểm tra Static + Playwright Vòng {qa_round} (0 token)",
            bubble_text=f"⚡ 0-token QA Vòng {qa_round}: Static & Playwright...",
            tool_call={
                "name": "offline_playwright_and_static_qa",
                "args": {"round": qa_round, "viewports": [1440, 768, 375]},
                "kind": "offline_script",
                "timestamp": utc_now_iso(),
            },
        )

        project_dir = PROJECTS_DIR / state.id
        preview_dir = project_dir / "preview_site"
        qa_target_dir = (
            Path(state.target_source_dir)
            if state.mode == "live_sdk" and state.preview_url and state.preview_url.startswith("http")
            else preview_dir
        )

        static_bugs, static_notes = run_static_checks(
            qa_target_dir, is_nasanic=(state.framework == "nasanic" or True)
        )
        local_url = self._resolve_local_qa_url(state)
        artifacts_dir = ARTIFACTS_DIR / state.id
        pw_bugs, screenshots, pw_metrics = await run_playwright_checks(
            local_url, artifacts_dir, state.id, qa_round
        )

        state.screenshots = screenshots
        state.token_stats.offline_steps_completed += 2
        self._recompute_token_stats(state)

        if state.enable_ai_vision_qa and screenshots:
            await self._update_agent(
                state,
                "qa",
                status="working_ai",
                execution_kind="ai",
                current_task=f"AI Vision QA Vòng {qa_round} (đối chiếu ảnh Playwright)",
                bubble_text=f"🤖 AI Vision QA Vòng {qa_round}...",
            )
            shot_paths = [
                str(artifacts_dir / f"round{qa_round}_{vp}.png")
                for vp in screenshots
            ]
            if state.mode == "live_sdk":
                vision_prompt = (
                    f"Kiểm tra trực quan ảnh chụp Playwright Vòng {qa_round}: {', '.join(shot_paths)}.\n"
                    f"Metrics: {json.dumps(pw_metrics, ensure_ascii=False)}\n"
                    f"Nhận xét ngắn gọn lỗi bố cục, chữ bị cắt, hoặc tương phản màu (nếu có)."
                )
                try:
                    vision_reply = await self._run_sdk_with_fallback(
                        state, "qa", vision_prompt, str(artifacts_dir)
                    )
                    await self._update_agent(
                        state,
                        "qa",
                        thought=f"AI Vision Vòng {qa_round}: {vision_reply[:280]}",
                    )
                    await self._log_timeline(
                        state,
                        "Tuấn (QA)",
                        f"AI Vision QA Vòng {qa_round}: {vision_reply[:160]}",
                        "ai",
                    )
                except Exception as exc:
                    await self._update_agent(
                        state,
                        "qa",
                        thought=f"AI Vision Vòng {qa_round} tạm bỏ qua ({exc}); giữ kết quả Offline QA.",
                    )
            else:
                state.token_stats.ai_calls_made += 1
                self._recompute_token_stats(state)
                await self._update_agent(
                    state,
                    "qa",
                    thought=(
                        f"AI Vision Vòng {qa_round}: đã đối chiếu {len(shot_paths)} ảnh "
                        f"Playwright ({', '.join(screenshots.keys())})."
                    ),
                )
                await self._log_timeline(
                    state,
                    "Tuấn (QA)",
                    f"Hoàn tất AI Vision QA Vòng {qa_round} trên {len(shot_paths)} ảnh chụp.",
                    "ai",
                )

        detected_raw = static_bugs + pw_bugs
        detected_ids = {b["id"] for b in detected_raw}

        # Preserve prior round history cleanly while updating active bugs
        existing_by_id = {b.id: b for b in state.bugs}
        updated_bugs: list[BugItem] = []

        # Keep ignored bugs as ignored (never nag user again)
        for old_bug in state.bugs:
            if old_bug.id in ignored_bug_ids or old_bug.status == "ignored":
                old_bug.status = "ignored"
                updated_bugs.append(old_bug)
            elif old_bug.status == "approved_for_fix" and old_bug.id not in detected_ids:
                old_bug.status = "fixed"
                updated_bugs.append(old_bug)
            elif old_bug.status == "fixed":
                updated_bugs.append(old_bug)

        already_in = {b.id for b in updated_bugs}
        for raw in detected_raw:
            b_id = raw["id"]
            if b_id in ignored_bug_ids:
                continue
            if b_id in already_in:
                continue
            prev = existing_by_id.get(b_id)
            if prev and prev.status == "approved_for_fix":
                status_val = "still_failing"
                note_val = prev.user_note
            else:
                status_val = "pending_review"
                note_val = prev.user_note if prev else ""

            updated_bugs.append(
                BugItem(
                    id=b_id,
                    title=raw["title"],
                    description=raw["description"],
                    severity=raw.get("severity", "major"),
                    source=raw.get("source", "offline_playwright"),
                    viewport=raw.get("viewport", "all"),
                    file_path=raw.get("file_path", ""),
                    selector_or_rule=raw.get("selector_or_rule", ""),
                    screenshot_url=raw.get("screenshot_url"),
                    assigned_role=raw.get("assigned_role", "dev"),
                    status=status_val,
                    user_note=note_val,
                    qa_round=qa_round,
                )
            )

        state.bugs = updated_bugs
        qa_task = next((t for t in state.tasks if t.owner_role == "qa"), None)
        if qa_task:
            qa_task.status = "done"

        await self._update_agent(
            state,
            "qa",
            thought=(
                f"Vòng {qa_round}: Static ({static_notes.get('css_files_checked', 0)} CSS, "
                f"PHP: {static_notes.get('php_lint')}); Playwright {len(pw_metrics.get('viewports_tested', []))} viewports. "
                f"Phát hiện {len([b for b in updated_bugs if b.status in ('pending_review', 'still_failing')])} lỗi cần xử lý."
            ),
        )

        actionable_bugs = [
            b for b in state.bugs if b.status in ("pending_review", "still_failing")
        ]

        if not actionable_bugs:
            await self._handoff_to_leader_and_relax(
                state, "qa", "Sạch lỗi! Đạt chuẩn 3 viewports"
            )
            await self._update_agent(
                state,
                "leader",
                status="done",
                location="leader_desk",
                bubble_text="🎉 Hoàn thành dự án!",
            )
            for aid in state.agents:
                if aid != "leader":
                    await self._update_agent(
                        state,
                        aid,
                        status="done",
                        location="lounge",
                        bubble_text="🎉 Xong dự án — đang giải trí!",
                    )
            await self._log_timeline(
                state,
                "Tuấn (QA)",
                f"Vòng {qa_round} đạt chuẩn — tất cả lỗi đã duyệt đều đã sạch!",
                "success",
            )
            await self._set_phase(state, "completed")
            return

        # Walk QA over to the 3D Bug Board and PAUSE for Human-in-the-loop Review!
        await self._walk_to(state, "qa", "bug_board", "📌 Treo danh sách lỗi lên Bug Board...")
        await self._update_agent(
            state,
            "qa",
            status="waiting_review",
            location="bug_board",
            current_task=f"Chờ bạn duyệt {len(actionable_bugs)} lỗi trên Bug Board",
            bubble_text=f"🟡 Chờ duyệt {len(actionable_bugs)} lỗi!",
        )
        await self._update_agent(
            state,
            "leader",
            status="waiting_review",
            bubble_text="🟡 Đợi bạn tick lỗi cần fix...",
        )
        await self._log_timeline(
            state,
            "Tuấn (QA)",
            f"QA Vòng {qa_round} phát hiện {len(actionable_bugs)} lỗi (0 token). Đang chờ bạn duyệt trên Bug Board.",
            "warning",
        )
        await self._set_phase(state, "waiting_bug_review")

    async def submit_bug_review(
        self, project_id: str, req: BugReviewRequest
    ) -> ProjectState:
        state = self.bus.get_project(project_id)
        if not state:
            raise KeyError("Project not found")
        if state.phase != "waiting_bug_review":
            raise ValueError(f"Project is in phase '{state.phase}', not 'waiting_bug_review'")

        decisions_map = {d.bug_id: d for d in req.decisions}
        approved_bugs: list[BugItem] = []

        for bug in state.bugs:
            if bug.status in ("fixed", "ignored"):
                continue
            dec = decisions_map.get(bug.id)
            if req.action_mode == "skip_and_complete":
                bug.status = "ignored"
                if dec and dec.user_note:
                    bug.user_note = dec.user_note
            elif dec and dec.action == "fix":
                bug.status = "approved_for_fix"
                bug.user_note = dec.user_note
                approved_bugs.append(bug)
            else:
                bug.status = "ignored"
                if dec and dec.user_note:
                    bug.user_note = dec.user_note

        if req.action_mode == "skip_and_complete" or not approved_bugs:
            for aid in state.agents:
                await self._update_agent(
                    state,
                    aid,
                    status="done",
                    location="leader_desk" if aid == "leader" else "lounge",
                    bubble_text=(
                        "🎉 Hoàn thành theo duyệt!"
                        if aid == "leader"
                        else "☕ Nghỉ ngơi ở phòng giải trí"
                    ),
                )
            await self._log_timeline(
                state,
                "Bạn (Reviewer)",
                "Đã duyệt bỏ qua các lỗi còn lại và chốt hoàn thành dự án.",
                "success",
            )
            await self._set_phase(state, "completed")
            return state

        await self._log_timeline(
            state,
            "Bạn (Reviewer)",
            f"Đã duyệt sửa {len(approved_bugs)} lỗi. Giao nhân viên quay lại sửa...",
            "info",
        )
        await self._set_phase(state, "fixing")

        task = asyncio.create_task(self._run_fix_and_retest(project_id, approved_bugs))
        self._tasks[project_id] = task
        return state

    async def _run_fix_and_retest(
        self, project_id: str, approved_bugs: list[BugItem]
    ) -> None:
        state = self.bus.get_project(project_id)
        if not state:
            return
        preview_dir = PROJECTS_DIR / project_id / "preview_site"

        try:
            def _resolve_assignee(bug: BugItem) -> AgentRole:
                if bug.assigned_role in state.agents:
                    return bug.assigned_role
                if "dev" in state.agents:
                    return "dev"
                return next(iter(state.agents))

            roles_needed: list[AgentRole] = list(
                dict.fromkeys(_resolve_assignee(b) for b in approved_bugs)
            )
            for r in roles_needed:
                role_bugs = [b for b in approved_bugs if _resolve_assignee(b) == r]
                await self._brief_at_leader(
                    state, r, f"Sửa {len(role_bugs)} lỗi đã duyệt"
                )
                await self._update_agent(
                    state,
                    r,
                    status="working_ai",
                    execution_kind="ai",
                    current_task=f"Sửa {len(role_bugs)} lỗi đã duyệt",
                    bubble_text=f"🔧 Đang fix {len(role_bugs)} lỗi...",
                    thought="Chỉ sửa đúng các lỗi đã được người dùng tick duyệt: "
                    + ", ".join(b.title for b in role_bugs),
                )

                if state.mode == "live_sdk":
                    fix_summary = "\n".join(
                        f"- [{b.id}] {b.title} ({b.file_path} | {b.selector_or_rule}) | Note: {b.user_note}"
                        for b in role_bugs
                    )
                    try:
                        await self._run_sdk_with_fallback(
                            state,
                            r,
                            f"Chỉ sửa các lỗi sau trong phạm vi phụ trách của bạn:\n{fix_summary}",
                            state.target_source_dir,
                        )
                    except Exception as sdk_exc:
                        await self._handle_sdk_error(state, r, sdk_exc)
                        return
                    if preview_dir.exists():
                        apply_demo_bug_fixes(preview_dir, role_bugs)
                else:
                    state.token_stats.ai_calls_made += 1
                    self._recompute_token_stats(state)
                    modified = apply_demo_bug_fixes(preview_dir, role_bugs)
                    for fpath in modified:
                        await self._update_agent(state, r, edited_file=fpath)
                    await asyncio.sleep(self.step_delay)

                await self._handoff_to_leader_and_relax(
                    state, r, f"Đã sửa xong {len(role_bugs)} lỗi"
                )

            ignored_ids = {b.id for b in state.bugs if b.status == "ignored"}
            await self._run_qa_pass(
                state, qa_round=state.qa_round + 1, ignored_bug_ids=ignored_ids
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.phase = "failed"
            state.error_message = str(exc)
            await self.bus.emit_project_sync(state, "fix_failed")

    async def _handle_sdk_error(
        self, state: ProjectState, agent_id: str, exc: Exception
    ) -> None:
        msg = f"Antigravity SDK báo lỗi: {exc}. Bạn có thể kiểm tra đăng nhập SDK hoặc chuyển sang chế độ Demo."
        state.agents[agent_id].chat_history.append(
            {"sender": "system", "text": msg, "timestamp": utc_now_iso()}
        )
        await self._update_agent(
            state,
            agent_id,
            status="blocked",
            bubble_text="🔴 SDK bị chặn/lỗi auth",
            thought=msg,
        )
        state.phase = "failed"
        state.error_message = msg
        await self._log_timeline(state, agent_id, msg, "error")
        await self.bus.emit_project_sync(state, "sdk_blocked")

    async def send_agent_chat(
        self, project_id: str, agent_id: str, message: str
    ) -> AgentState:
        state = self.bus.get_project(project_id)
        if not state:
            raise KeyError("Project not found")
        if agent_id not in state.agents:
            raise KeyError("Agent not found")

        agent = state.agents[agent_id]
        agent.chat_history.append(
            {"sender": "user", "text": message, "timestamp": utc_now_iso()}
        )
        await self.bus.emit_project_sync(state, "agent_chat_user")

        if state.mode == "live_sdk":
            try:
                reply = await self._run_sdk_with_fallback(
                    state,
                    agent_id,
                    f"Người dùng nhắn trực tiếp cho bạn: {message}\nTask hiện tại: {agent.current_task}",
                    state.target_source_dir,
                )
            except Exception as exc:
                reply = f"Không gọi được Live SDK ({exc}). Hãy thử chạy Demo mode hoặc kiểm tra cấu hình SDK."
        else:
            reply = (
                f"[{agent.name}] Đã nhận chỉ dẫn: \"{message}\". "
                f"Trạng thái hiện tại: {agent.status} | Task: {agent.current_task or 'Đang chờ'}."
            )

        agent.chat_history.append(
            {"sender": "agent", "text": reply, "timestamp": utc_now_iso()}
        )
        await self.bus.emit_project_sync(state, "agent_chat_reply")
        return agent
