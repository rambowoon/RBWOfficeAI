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
    assert "figma_token_configured" in data
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


def test_parse_xls_upload_and_structured_classification(monkeypatch) -> None:
    import types
    import xlrd
    from app.offline.spec_parser import parse_structured_spec, reconcile_figma_and_spec

    class _FakeSheet:
        name = "Sheet1"
        nrows = 8
        ncols = 3
        _rows = [
            ["", "TÊN HỢP ĐỒNG", "SPA TEST"],
            ["", "TÊN NVKD", "NGUYỄN VĂN A - 0909123456"],
            ["STT", "TÊN CHỨC NĂNG", "MÔ TẢ CHI TIẾT CHỨC NĂNG"],
            [1.0, "GIỚI THIỆU", "Dạng một bài viết giới thiệu, nhập 1 ảnh"],
            [2.0, "Menu", "Danh mục 1 cấp, ảnh sản phẩm có đóng dấu logo, k hiện giá"],
            [3.0, "Tin tức", "Dạng nhiều bài viết như demo"],
            [4.0, "Album", "Dạng 1 Album nhiều ảnh, ấn vào hiện popup"],
            [5.0, "Note", "Tối ưu ảnh tự động"],
        ]

        def cell_value(self, r: int, c: int):
            return self._rows[r][c]

    class _FakeBook:
        def sheets(self):
            return [_FakeSheet()]

    monkeypatch.setattr(xlrd, "open_workbook", lambda file_contents=None: _FakeBook())

    client = TestClient(app)
    resp = client.post(
        "/api/specs/parse",
        files={"file": ("spec.xls", b"FAKE_XLS_BYTES", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "Menu | Danh mục 1 cấp" in payload["text"]
    assert "TÊN NVKD" in payload["text"]

    structured = payload["structured"]
    assert structured["metadata"]["contract_name"] == "SPA TEST"
    items_by_name = {i["name"]: i for i in structured["items"]}
    assert "TÊN NVKD" not in items_by_name
    assert items_by_name["GIỚI THIỆU"]["content_type"] == "article_single"
    assert items_by_name["GIỚI THIỆU"]["item_cardinality"] == "single"
    assert items_by_name["Menu"]["content_type"] == "product"
    assert items_by_name["Menu"]["category_levels"] == 1
    assert "Không hiện giá" in items_by_name["Menu"]["notes"]
    assert "Đóng dấu logo" in items_by_name["Menu"]["notes"]
    assert items_by_name["Tin tức"]["content_type"] == "article_list"
    assert items_by_name["Tin tức"]["item_cardinality"] == "multiple"
    assert items_by_name["Album"]["content_type"] == "album"
    assert "Tối ưu ảnh tự động" in structured["global_features"]

    # Real sample files smoke-check if present on workstation
    real_xls = Path(r"c:\Users\nina\Desktop\dacta\doan-thi-kim-tai-thien-1666326-17877257847118.xls")
    if real_xls.exists():
        monkeypatch.undo()
        r_real = client.post(
            "/api/specs/parse",
            files={"file": (real_xls.name, real_xls.read_bytes(), "application/vnd.ms-excel")},
        )
        assert r_real.status_code == 200
        assert r_real.json()["structured"]["metadata"]["contract_name"] == "ĐOÀN THỊ KIM TÀI THIÊN"

    # Reconcile Figma-first ordering: Figma sections come first, unmatched flagged figma_only, remaining spec_only
    tokens_data = {
        "sections": [
            {"id": "1", "name": "Header Navigation"},
            {"id": "2", "name": "San Pham Noi Bat"},
            {"id": "3", "name": "Ve Chung Toi"},
        ]
    }
    rec = reconcile_figma_and_spec(tokens_data, payload["text"])
    sec_list = rec["spec_sections"]
    assert [s["figma_section_name"] for s in sec_list[:3]] == [
        "Header Navigation",
        "San Pham Noi Bat",
        "Ve Chung Toi",
    ]
    assert sec_list[0]["source"] == "figma_only"
    assert sec_list[1]["source"] == "figma_and_spec"
    assert sec_list[1]["content_type"] == "product"
    assert sec_list[1]["category_levels"] == 1
    assert sec_list[2]["source"] == "figma_and_spec"
    assert sec_list[2]["content_type"] == "article_single"
    assert any(s["source"] == "spec_only" and s["name"] == "Tin tức" for s in sec_list)

    # Ensure parse_structured_spec works on clean tabular text directly too
    parsed_direct = parse_structured_spec(payload["text"])
    assert len(parsed_direct["items"]) == 4


def test_approve_plan_persists_edited_spec_sections(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app import event_bus as eb_mod
    from app.agents import orchestrator as orch_mod
    from app.agents.orchestrator import OfficeOrchestrator
    from app.models import SpecSectionItem

    projects_root = tmp_path / "projects"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(eb_mod, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(orch_mod, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(orch_mod, "ARTIFACTS_DIR", artifacts_root)

    async def _fake_playwright(preview_url: str, artifacts_dir: Path, project_id: str, qa_round: int):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return [], {}, {"viewports_tested": ["desktop", "tablet", "mobile"]}

    monkeypatch.setattr(orch_mod, "run_playwright_checks", _fake_playwright)

    async def _run() -> None:
        local_bus = eb_mod.EventBus()
        orch = OfficeOrchestrator(bus=local_bus, step_delay=0.0, walk_delay=0.0)
        req = ProjectCreate(
            name="Structured Spec Review Test",
            spec_text="1 | Menu | Danh mục 1 cấp, k hiện giá\n2 | Giới thiệu | Dạng một bài viết",
            figma_url="https://www.figma.com/design/DEMOKEY123/Test",
            target_source_dir=str(tmp_path),
            mode="demo",
        )
        state = await orch.create_and_start(req)
        await orch._tasks[state.id]
        assert state.phase == "waiting_plan_review"
        assert len(state.spec_sections) >= 3

        custom_sections = [
            SpecSectionItem(
                id="sec-1",
                order=1,
                name="Danh mục sản phẩm chính",
                scope="homepage",
                source="figma_and_spec",
                figma_section_name="San Pham Noi Bat",
                content_type="product",
                category_levels=2,
                item_cardinality="multiple",
                spec_requirements="Nâng cấp thành danh mục 2 cấp, hiển thị giá",
                notes="Có hiển thị giá",
            )
        ]
        updated = await orch.approve_leader_plan(
            state.id,
            PlanApprovalRequest(
                leader_plan_markdown="",
                spec_sections=custom_sections,
                spec_global_features=["SEO chuẩn Google", "Nén WebP tự động"],
            ),
        )
        assert updated.spec_sections[0].category_levels == 2
        assert "Danh mục sản phẩm chính" in updated.leader_plan_markdown
        saved_json = json.loads(
            (projects_root / state.id / "spec_sections.json").read_text(encoding="utf-8")
        )
        assert saved_json["sections"][0]["category_levels"] == 2
        assert saved_json["global_features"] == ["SEO chuẩn Google", "Nén WebP tự động"]
        await orch._tasks[state.id]

    asyncio.run(_run())


def test_live_sdk_leader_updates_spec_section_cards_and_user_can_edit(
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

    async def _run() -> None:
        local_bus = eb_mod.EventBus()
        orch = OfficeOrchestrator(bus=local_bus, step_delay=0.0, walk_delay=0.0)

        async def _fake_sdk(state, agent_id: str, prompt: str, working_dir=None) -> str:
            return """```json
{
  "spec_sections": [
    {
      "id": "sec-1",
      "order": 1,
      "name": "Sản phẩm Spa cao cấp",
      "scope": "homepage",
      "source": "figma_and_spec",
      "figma_section_name": "San Pham Noi Bat",
      "content_type": "product",
      "category_levels": 2,
      "item_cardinality": "multiple",
      "spec_requirements": "AI đã phân tích lại: sản phẩm 2 cấp danh mục, có giá",
      "notes": "Có hiển thị giá · Đóng dấu logo"
    },
    {
      "id": "sec-2",
      "order": 2,
      "name": "Tin tức làm đẹp",
      "scope": "homepage",
      "source": "spec_only",
      "figma_section_name": "",
      "content_type": "article_list",
      "category_levels": 1,
      "item_cardinality": "multiple",
      "spec_requirements": "Nhiều bài viết chia 1 cấp danh mục",
      "notes": ""
    }
  ],
  "spec_global_features": ["SEO chuẩn Google", "Icon Zalo/Mess"]
}
```"""

        monkeypatch.setattr(orch, "_run_sdk_with_fallback", _fake_sdk)

        req = ProjectCreate(
            name="Live AI Cards Test",
            spec_text="1 | Sản phẩm | Mô tả sơ bộ",
            figma_url="https://www.figma.com/design/DEMOKEY123/Test",
            target_source_dir=str(tmp_path),
            mode="live_sdk",
        )
        state = await orch.create_and_start(req)
        await orch._tasks[state.id]

        assert state.phase == "waiting_plan_review"
        assert len(state.spec_sections) == 2
        assert state.spec_sections[0].name == "Sản phẩm Spa cao cấp"
        assert state.spec_sections[0].category_levels == 2
        assert state.spec_sections[1].content_type == "article_list"
        assert state.spec_global_features == ["SEO chuẩn Google", "Icon Zalo/Mess"]
        assert "Sản phẩm Spa cao cấp" in state.leader_plan_markdown

        saved = json.loads(
            (projects_root / state.id / "spec_sections.json").read_text(encoding="utf-8")
        )
        assert saved["sections"][0]["name"] == "Sản phẩm Spa cao cấp"
        assert saved["sections"][0]["category_levels"] == 2

    asyncio.run(_run())


def test_workspace_folder_picker_and_live_sdk_requires_source_dir(monkeypatch) -> None:
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "_open_folder_dialog", lambda: r"D:\RBWStudio\www\my_site")
    client = TestClient(app)

    r_pick = client.post("/api/workspace/pick-folder")
    assert r_pick.status_code == 200
    assert r_pick.json() == {"path": r"D:\RBWStudio\www\my_site", "cancelled": False}

    r_create = client.post(
        "/api/projects",
        json={
            "name": "Missing Source Test",
            "spec_text": "1 | Trang chủ | Demo",
            "figma_url": "",
            "target_source_dir": "",
            "mode": "live_sdk",
        },
    )
    assert r_create.status_code == 400
    assert "Source" in r_create.json()["detail"]


def test_menu_and_major_homepage_extraction_filters_junk_frames_and_coding_reqs() -> None:
    from app.offline.spec_parser import reconcile_figma_and_spec

    # Raw Figma payload mixing whole-page canvas ("demo"), tiny atoms ("Hotline", "Email", "SP 1", "Tab"),
    # a real Menu container, and 2 major homepage bands.
    raw_figma = {
        "name": "Co Khi Test",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "1:2",
                            "name": "demo",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"width": 1920, "height": 5901, "y": 0},
                            "children": [
                                {
                                    "id": "2:21",
                                    "name": "Hotline",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 125, "height": 16, "y": 10},
                                    "children": [],
                                },
                                {
                                    "id": "2:37",
                                    "name": "Email",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 234, "height": 16, "y": 10},
                                    "children": [],
                                },
                                {
                                    "id": "2:82",
                                    "name": "Menu",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 646, "height": 18, "y": 40},
                                    "children": [
                                        {"id": "m1", "type": "TEXT", "characters": "Trang chủ", "absoluteBoundingBox": {"x": 10, "y": 40}},
                                        {"id": "m2", "type": "TEXT", "characters": "Giới thiệu", "absoluteBoundingBox": {"x": 100, "y": 40}},
                                        {"id": "m3", "type": "TEXT", "characters": "Sản phẩm", "absoluteBoundingBox": {"x": 200, "y": 40}},
                                        {"id": "m4", "type": "TEXT", "characters": "Tin tức", "absoluteBoundingBox": {"x": 300, "y": 40}},
                                    ],
                                },
                                {
                                    "id": "3:10",
                                    "name": "Hero Slide",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 1920, "height": 620, "y": 100},
                                    "children": [
                                        {
                                            "id": "4:330",
                                            "name": "SP 1",
                                            "type": "FRAME",
                                            "absoluteBoundingBox": {"width": 300, "height": 410, "y": 200},
                                            "children": [],
                                        }
                                    ],
                                },
                                {
                                    "id": "3:20",
                                    "name": "Sản phẩm nổi bật",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 1920, "height": 720, "y": 800},
                                    "children": [],
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }
    compact = extract_compact_tokens(raw_figma)
    assert compact["menu_items"] == ["Trang chủ", "Giới thiệu", "Sản phẩm", "Tin tức"]
    section_names = [s["name"] for s in compact["sections"]]
    assert section_names == ["Hero Slide", "Sản phẩm nổi bật"]
    for junk in ("demo", "Hotline", "Email", "SP 1", "Menu"):
        assert junk not in section_names

    spec_text = (
        "TÊN HỢP ĐỒNG | | CƠ KHÍ TEST\n"
        "STT | TÊN CHỨC NĂNG | MÔ TẢ CHI TIẾT | KHÁCH HÀNG\n"
        "1 | Header | Logo tráng gương, tìm kiếm trong trang | OK\n"
        "2 | | Trang chủ : chuyển về trang chủ Giới thiệu: Một bài viết Sản phẩm: 2 cấp Tin tức: Nhiều bài viết Dịch vụ: nhiều bài viết Liên hệ: Form cơ bản | OK\n"
        "3 | Slide | Slide video chạy vòng lặp | OK\n"
        "5 | Sản phẩm nổi bật | Hình ảnh và tên sản phẩm nhập trong admin | OK\n"
        "13 | Footer | Nội dung nhập trong admin | OK\n"
        " | | 1. Fanpage và Zalo, maps gắn link | OK\n"
        "YÊU CẦU LẬP TRÌNH | | - Giao diện responsive tối đa 1920px |\n"
        " | | - Lập trình bằng PHP >= 8.3 |\n"
        " | | - Hệ thống Admin đầy đủ SEO |\n"
    )

    rec = reconcile_figma_and_spec(compact, spec_text)
    secs = rec["spec_sections"]
    names = [s["name"] for s in secs]

    # Zero bogus "Mục bổ sung" or junk micro-frames
    assert "Mục bổ sung" not in names
    assert all(s["name"] not in {"demo", "Hotline", "Email", "SP 1"} for s in secs)

    # Menu items properly classified
    menu_secs = {s["name"]: s for s in secs if s["scope"] == "menu"}
    assert "Menu: Giới thiệu" in menu_secs
    assert menu_secs["Menu: Giới thiệu"]["content_type"] == "article_single"
    assert menu_secs["Menu: Sản phẩm"]["content_type"] == "product"
    assert menu_secs["Menu: Sản phẩm"]["category_levels"] == 2
    assert menu_secs["Menu: Tin tức"]["content_type"] == "article_list"
    assert menu_secs["Menu: Dịch vụ"]["content_type"] == "article_list"
    assert menu_secs["Menu: Liên hệ"]["content_type"] == "form"

    # Continuation row appended to Footer instead of spawning a new card
    footer = next(s for s in secs if s["name"] == "Footer")
    assert "Fanpage và Zalo" in footer["spec_requirements"]

    # Coding & SEO requirements routed into global_features
    assert any("PHP >= 8.3" in g for g in rec["spec_global_features"])
    assert any("SEO" in g for g in rec["spec_global_features"])
