from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, bus
from app.models import (
    BugDecisionItem,
    BugItem,
    BugReviewRequest,
    PlanApprovalRequest,
    PlanTaskUpdate,
    ProjectCreate,
    ProjectState,
    build_default_agents,
)
from app.offline.figma_parser import extract_compact_tokens, parse_figma_url
from app.offline.qa_runner import run_static_checks
from app.offline.source_scaffold import apply_demo_bug_fixes


def test_parse_figma_url_extracts_key_and_node_id() -> None:
    key, node = parse_figma_url(
        "https://www.figma.com/design/AbCdEf12345/Landing-Page?node-id=12-345&t=xyz"
    )
    assert key == "AbCdEf12345"
    assert node == "12:345"

    key2, node2 = parse_figma_url("https://www.figma.com/file/Z99X/Demo")
    assert key2 == "Z99X"
    assert node2 is None


def test_extract_compact_tokens_strips_invisible_nodes() -> None:
    raw_figma = {
        "name": "Demo Site",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "1:1",
                            "name": "Hero Section",
                            "type": "FRAME",
                            "layoutMode": "HORIZONTAL",
                            "absoluteBoundingBox": {"width": 1440, "height": 600},
                            "fills": [
                                {"type": "SOLID", "color": {"r": 0.1, "g": 0.3, "b": 0.8, "a": 1}}
                            ],
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "Hero Title",
                                    "type": "TEXT",
                                    "style": {
                                        "fontFamily": "Be Vietnam Pro",
                                        "fontSize": 40,
                                        "fontWeight": 700,
                                        "lineHeightPx": 50,
                                    },
                                },
                                {
                                    "id": "1:3",
                                    "name": "Hidden Draft Layer",
                                    "type": "FRAME",
                                    "visible": False,
                                    "children": [
                                        {
                                            "id": "1:4",
                                            "type": "TEXT",
                                            "style": {"fontFamily": "Comic Sans MS", "fontSize": 99},
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }
    compact = extract_compact_tokens(raw_figma)
    assert compact["fonts"] == ["Be Vietnam Pro"]
    assert "Comic Sans MS" not in compact["fonts"]
    assert compact["stats"]["raw_node_count"] == 5
    assert compact["stats"]["kept_node_count"] == 4
    assert len(compact["sections"]) == 1


def test_static_checks_detect_forbidden_aspect_ratio(tmp_path: Path) -> None:
    css_dir = tmp_path / "assets" / "css"
    css_dir.mkdir(parents=True)
    (css_dir / "style.css").write_text(".box { aspect-ratio: 16/9; }", encoding="utf-8")

    bugs, notes = run_static_checks(tmp_path, is_nasanic=True)
    assert notes["css_files_checked"] == 1
    assert any(b["id"] == "bug-css-aspect-ratio" for b in bugs)


def test_figma_token_never_serialized_or_persisted(tmp_path: Path, monkeypatch) -> None:
    from app import event_bus as eb_mod

    monkeypatch.setattr(eb_mod, "PROJECTS_DIR", tmp_path)
    test_bus = eb_mod.EventBus()

    req = ProjectCreate(
        name="Secret Check",
        spec_text="Test spec",
        figma_url="https://www.figma.com/design/ABC/Test",
        figma_token="figd_SUPER_SECRET_TOKEN_XYZ",
        target_source_dir=str(tmp_path),
        mode="demo",
    )
    assert "figma_token" not in ProjectState.model_fields

    state = ProjectState(
        id="p-secret",
        name=req.name,
        spec_text=req.spec_text,
        figma_url=req.figma_url,
        target_source_dir=req.target_source_dir,
        agents=build_default_agents(),
    )
    test_bus.save_project(state)
    saved_text = (tmp_path / "p-secret" / "state.json").read_text(encoding="utf-8")
    assert "figd_SUPER_SECRET_TOKEN_XYZ" not in saved_text
    assert "figma_token" not in json.loads(saved_text)


def test_selective_demo_bug_fixes_only_touches_approved(tmp_path: Path) -> None:
    (tmp_path / "assets" / "css").mkdir(parents=True)
    style = tmp_path / "assets" / "css" / "style.css"
    style.write_text(
        ".hero { aspect-ratio: 16 / 9; }\n.promo { min-width: 520px; }\n",
        encoding="utf-8",
    )
    html = tmp_path / "index.html"
    html.write_text('<img src="assets/images/missing-banner-404.webp">', encoding="utf-8")

    approved = [
        BugItem(
            id="bug-css-aspect-ratio",
            title="Forbidden aspect-ratio",
            description="desc",
            selector_or_rule="aspect-ratio",
        )
    ]
    modified = apply_demo_bug_fixes(tmp_path, approved)
    assert modified == ["assets/css/style.css"]
    updated_css = style.read_text(encoding="utf-8")
    assert "aspect-ratio" not in updated_css
    assert "min-width: 520px;" in updated_css
    assert "missing-banner-404.webp" in html.read_text(encoding="utf-8")


def test_health_endpoint_reports_sdk_and_playwright() -> None:
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "sdk" in data
    assert data["playwright_ready"] is True


def test_parse_spec_upload_docx_and_xlsx() -> None:
    import io
    import zipfile

    client = TestClient(app)

    # Minimal valid .docx
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Trang chủ Nasanic</w:t></w:r></w:p></w:body></w:document>",
        )
    r_docx = client.post(
        "/api/specs/parse",
        files={"file": ("spec.docx", docx_buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r_docx.status_code == 200
    assert "Trang chủ Nasanic" in r_docx.json()["text"]

    # Minimal valid .xlsx
    xlsx_buf = io.BytesIO()
    with zipfile.ZipFile(xlsx_buf, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Section</t></si><si><t>Hero Banner</t></si></sst>',
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row></sheetData></worksheet>',
        )
    r_xlsx = client.post(
        "/api/specs/parse",
        files={"file": ("spec.xlsx", xlsx_buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r_xlsx.status_code == 200
    assert "Section | Hero Banner" in r_xlsx.json()["text"]


def test_default_agents_four_member_roster_and_lounge_location() -> None:
    from app.models import AgentState

    agents = build_default_agents()
    assert list(agents.keys()) == ["leader", "asset", "dev", "qa"]
    assert agents["leader"].location == "leader_desk"

    lounge_agent = AgentState(
        id="dev",
        name="Vy (UI & Frontend)",
        role="dev",
        title="HTML/Blade, CSS & Responsive",
        status="done",
        location="lounge",
    )
    assert lounge_agent.location == "lounge"


def test_demo_pipeline_four_agents_lounge_and_selective_fix_flow(
    tmp_path: Path, monkeypatch
) -> None:
    import asyncio
    from app import event_bus as eb_mod
    from app.agents import orchestrator as orch_mod
    from app.agents.orchestrator import OfficeOrchestrator

    projects_root = tmp_path / "projects"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(eb_mod, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(orch_mod, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(orch_mod, "ARTIFACTS_DIR", artifacts_root)

    async def _fake_playwright(
        preview_url: str, artifacts_dir: Path, project_id: str, qa_round: int
    ):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        shots = {
            vp: f"/artifacts/{project_id}/round{qa_round}_{vp}.png"
            for vp in ("desktop", "tablet", "mobile")
        }
        metrics = {"viewports_tested": ["desktop", "tablet", "mobile"]}
        if qa_round == 1:
            pw_bugs = [
                {
                    "id": "bug-mobile-overflow",
                    "title": "Tràn ngang màn hình Mobile (+145px)",
                    "description": "Mobile overflow",
                    "severity": "critical",
                    "source": "offline_playwright",
                    "viewport": "mobile",
                    "file_path": "assets/css/style.css",
                    "selector_or_rule": ".promo-ribbon",
                    "screenshot_url": shots["mobile"],
                    "assigned_role": "dev",
                },
                {
                    "id": "bug-missing-img-404",
                    "title": "Ảnh bị vỡ / không tải được (missing-banner-404.webp)",
                    "description": "404 image",
                    "severity": "critical",
                    "source": "offline_playwright",
                    "viewport": "desktop",
                    "file_path": "index.html",
                    "selector_or_rule": "assets/images/missing-banner-404.webp",
                    "screenshot_url": shots["desktop"],
                    "assigned_role": "asset",
                },
            ]
            return pw_bugs, shots, metrics
        return [], shots, metrics

    monkeypatch.setattr(orch_mod, "run_playwright_checks", _fake_playwright)

    async def _run_flow() -> None:
        import pytest

        local_bus = eb_mod.EventBus()
        orch = OfficeOrchestrator(bus=local_bus, step_delay=0.0, walk_delay=0.0)
        req = ProjectCreate(
            name="E2E 4-Agent Test",
            spec_text="- Hero banner + 3 gói dịch vụ + Form tư vấn.",
            figma_url="https://www.figma.com/design/DEMOKEY123/Test?node-id=1-1",
            target_source_dir=str(tmp_path),
            mode="demo",
            enable_ai_vision_qa=True,
        )
        state = await orch.create_and_start(req)
        await orch._tasks[state.id]

        # Gate 1: Leader analyzed spec & Figma, paused at waiting_plan_review before assigning staff
        assert (projects_root / state.id / "tokens.json").exists()
        plan_file = projects_root / state.id / "leader_plan.md"
        assert plan_file.exists()
        assert state.phase == "waiting_plan_review"
        assert state.plan_approved is False
        assert "ĐẶC TẢ PHÂN TÍCH DỰ ÁN" in state.leader_plan_markdown
        assert state.agents["leader"].status == "waiting_review"
        for staff_id in ("asset", "dev", "qa"):
            assert state.agents[staff_id].status == "idle"
            assert state.agents[staff_id].location == "desk"

        # User edits analyzed plan + task title, then approves
        edited_markdown = (
            f"{state.leader_plan_markdown}\n\n- Bổ sung mục Cam kết bảo hành 5 năm."
        )
        await orch.approve_leader_plan(
            state.id,
            PlanApprovalRequest(
                leader_plan_markdown=edited_markdown,
                tasks=[
                    PlanTaskUpdate(
                        id="t-dev",
                        title="Code HTML/CSS + Bảo hành 5 năm",
                        detail="Giữ responsive 3 viewports",
                    )
                ],
                user_note="Ưu tiên mục bảo hành ngay dưới giới thiệu.",
            ),
        )
        assert "Bổ sung mục Cam kết bảo hành 5 năm." in state.leader_plan_markdown
        assert "Bổ sung mục Cam kết bảo hành 5 năm." in plan_file.read_text(encoding="utf-8")
        assert state.plan_approved is True

        with pytest.raises(ValueError):
            await orch.approve_leader_plan(
                state.id,
                PlanApprovalRequest(leader_plan_markdown=edited_markdown),
            )

        await orch._tasks[state.id]

        # Gate 2: Staff finished -> QA found bugs -> paused at waiting_bug_review
        assert (projects_root / state.id / "preview_site" / "data" / "seed.json").exists()
        assert state.phase == "waiting_bug_review"
        assert state.agents["asset"].location == "lounge"
        assert state.agents["asset"].status == "done"
        assert state.agents["dev"].location == "lounge"
        assert state.agents["dev"].status == "done"
        assert state.agents["qa"].location == "bug_board"
        assert state.agents["qa"].status == "waiting_review"

        bug_ids = [b.id for b in state.bugs]
        assert "bug-css-aspect-ratio" in bug_ids
        assert "bug-mobile-overflow" in bug_ids
        assert "bug-missing-img-404" in bug_ids

        chatted = await orch.send_agent_chat(state.id, "dev", "Kiểm tra CSS Nasanic")
        assert len(chatted.chat_history) == 2
        assert "Vy (UI & Frontend)" in chatted.chat_history[-1]["text"]

        await orch.submit_bug_review(
            state.id,
            BugReviewRequest(
                action_mode="fix_selected",
                decisions=[
                    BugDecisionItem(bug_id=bid, action="fix") for bid in bug_ids
                ],
            ),
        )
        await orch._tasks[state.id]

        assert state.phase == "completed"
        assert state.qa_round == 2
        assert state.agents["leader"].location == "leader_desk"
        assert state.agents["leader"].status == "done"
        for staff_id in ("asset", "dev", "qa"):
            assert state.agents[staff_id].location == "lounge"
            assert state.agents[staff_id].status == "done"
        assert state.token_stats.ai_calls_made >= 3

    asyncio.run(_run_flow())
