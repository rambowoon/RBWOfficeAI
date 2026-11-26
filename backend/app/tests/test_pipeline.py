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
    (css_dir / "style-tailwind.css").write_text(".aspect-square { aspect-ratio: 1/1; }", encoding="utf-8")
    (css_dir / "bootstrap.min.css").write_text(".ratio { aspect-ratio: 16/9; }", encoding="utf-8")
    (css_dir / "style.css").write_text(".box { aspect-ratio: 16/9; }", encoding="utf-8")

    bugs, notes = run_static_checks(tmp_path, is_nasanic=True)
    assert notes["css_files_checked"] == 1
    assert any(b["id"] == "bug-css-aspect-ratio" and b["file_path"] == "assets/css/style.css" for b in bugs)


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


def test_agy_cli_runner_parses_stream_json_without_gemini_key(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app.agents import sdk_adapter as sa_mod

    monkeypatch.setattr(sa_mod, "_find_agy_cli", lambda: r"C:\Users\nina\.gemini\bin\agy.exe")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    status = sa_mod.check_sdk_status()
    assert status["available"] is True
    assert status.get("backend") == "cli"

    ndjson_lines = [
        b'{"event":"init","conversation_id":"abc-123"}\n',
        b'{"event":"step_update","step_update":{"step_type":"thought","thought":"Inspecting workspace"}}\n',
        b'{"event":"step_update","step_update":{"step_index":2,"state":"ACTIVE","step_type":"tool","tool_name":"run_command","tool_info":{"name":"run_command","parameters":{"CommandLine":"echo hi"}}}}\n',
        b'{"event":"step_update","step_update":{"step_index":2,"state":"DONE","step_type":"tool","tool_name":"run_command","tool_info":{"name":"run_command","parameters":{"CommandLine":"echo hi"},"output":"hi"}}}\n',
        b'{"event":"step_update","step_update":{"step_type":"tool_call","tool_name":"write_to_file","tool_args":{"path":"index.html"}}}\n',
        b'{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"DONE_"}}\n',
        b'{"event":"result","result":{"status":"SUCCESS","response":"DONE_FROM_CLI"}}\n',
        b"",
    ]

    class _FakeStream:
        def __init__(self, lines):
            self._lines = list(lines)

        def readline(self):
            return self._lines.pop(0) if self._lines else b""

        def read(self):
            return b""

    class _FakeProc:
        stdout = _FakeStream(ndjson_lines)
        stderr = _FakeStream([])

        def poll(self):
            return 0

        def wait(self):
            return 0

    captured_cmd = []

    def _fake_popen(args, **kwargs):
        captured_cmd.extend(args)
        return _FakeProc()

    monkeypatch.setattr(sa_mod.subprocess, "Popen", _fake_popen)

    thoughts = []
    tools = []

    async def _on_thought(t: str) -> None:
        thoughts.append(t)

    async def _on_tool(c: dict) -> None:
        tools.append(c)

    async def _run() -> str:
        runner = sa_mod.AntigravityAgentRunner()
        return await runner.run_task(
            system_instructions="You are Vy",
            prompt="Build homepage",
            working_dir=str(tmp_path),
            on_thought=_on_thought,
            on_tool_call=_on_tool,
        )

    out = asyncio.run(_run())
    assert out == "DONE_FROM_CLI"
    assert thoughts == ["Inspecting workspace"]
    assert len(tools) == 2
    assert tools[0]["name"] == "run_command"
    assert tools[0]["args"] == {"CommandLine": "echo hi"}
    assert tools[1]["name"] == "write_to_file"
    assert tools[1]["args"] == {"path": "index.html"}
    assert "--output-format" in captured_cmd
    assert "stream-json" in captured_cmd
    assert "--dangerously-skip-permissions" in captured_cmd
    assert "--add-dir" in captured_cmd

    # When agy CLI is missing, report unavailable & raise explicitly (no Python SDK fallback)
    import pytest

    monkeypatch.setattr(sa_mod, "_find_agy_cli", lambda: None)
    missing_status = sa_mod.check_sdk_status()
    assert missing_status["available"] is False
    assert "agy" in missing_status["detail"].lower()

    with pytest.raises(RuntimeError, match="agy"):
        asyncio.run(
            sa_mod.AntigravityAgentRunner().run_task(
                system_instructions="sys", prompt="hello"
            )
        )


def test_figma_image_dimensions_and_nasanic_config_type_generation(tmp_path: Path) -> None:
    from app.models import SpecSectionItem
    from app.offline.nasanic_configurator import configure_nasanic_types

    raw_figma = {
        "name": "Nasanic Dimensions",
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
                            "name": "Slide",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"width": 1920, "height": 680, "y": 0},
                            "fills": [{"type": "IMAGE"}],
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "san-pham",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"width": 450, "height": 320, "y": 100},
                                    "fills": [{"type": "IMAGE"}],
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    compact = extract_compact_tokens(raw_figma)
    assert compact["image_dimensions"]["slide"] == {"width": 1920, "height": 680}
    assert compact["image_dimensions"]["san-pham"] == {"width": 450, "height": 320}

    spec_sections = [
        SpecSectionItem(
            id="sec-1",
            order=1,
            name="Menu: Sản phẩm",
            scope="menu",
            source="figma_and_spec",
            content_type="product",
            category_levels=2,
            item_cardinality="multiple",
            spec_requirements="2 cấp danh mục",
            notes="Không hiện giá · Đóng dấu logo",
        ),
        SpecSectionItem(
            id="sec-2",
            order=2,
            name="Menu: Tin tức",
            scope="menu",
            source="spec_only",
            content_type="article_list",
            category_levels=1,
            item_cardinality="multiple",
            spec_requirements="Nhiều bài viết 1 cấp",
        ),
        SpecSectionItem(
            id="sec-3",
            order=3,
            name="Giới thiệu",
            scope="homepage",
            source="spec_only",
            content_type="article_single",
            category_levels=0,
            item_cardinality="single",
            spec_requirements="1 bài viết giới thiệu",
        ),
    ]

    cfg_dir = tmp_path / "config"
    summary = configure_nasanic_types(
        cfg_dir,
        spec_sections,
        compact,
        {"dimensions": compact["image_dimensions"]},
        ["Tối ưu ảnh tự động"],
    )
    assert summary["watermark_enabled"] is True
    assert set(summary["written_files"]) == {
        "config/type-products.php",
        "config/type-news.php",
        "config/type-static.php",
        "config/type-photo.php",
        "config/type-newsletters.php",
    }

    prod_php = (cfg_dir / "type-products.php").read_text(encoding="utf-8")
    assert "'san-pham' =>" in prod_php
    assert "'width' => 800" in prod_php
    assert "'height' => 569" in prod_php
    assert "'thumb' => '800x569x1'" in prod_php
    assert "'regular_price' => false" in prod_php
    assert "'list' =>" in prod_php
    assert "'cat' =>" in prod_php

    news_php = (cfg_dir / "type-news.php").read_text(encoding="utf-8")
    assert "'tin-tuc' =>" in news_php
    assert "'dropdown' => true" in news_php
    assert "'list' =>" in news_php

    photo_php = (cfg_dir / "type-photo.php").read_text(encoding="utf-8")
    assert "'watermark_product' =>" in photo_php

    # Verify options2 generation (video_mp4 on slideshow, statistical on stats section, link-youtube on video)
    opts2_sections = [
        SpecSectionItem(
            id="s1",
            order=1,
            name="Slide",
            scope="homepage",
            source="spec_only",
            content_type="layout",
            spec_requirements="1. Slide: Dạng video chạy vòng lặp mp4",
        ),
        SpecSectionItem(
            id="s2",
            order=2,
            name="Vì sao chọn chúng tôi",
            scope="homepage",
            source="spec_only",
            content_type="feature",
            spec_requirements="Hiệu ứng những con số số liệu nhảy liên tục",
        ),
        SpecSectionItem(
            id="s3",
            order=3,
            name="Video clip",
            scope="homepage",
            source="spec_only",
            content_type="video",
            spec_requirements="Link từ YouTube qua",
        ),
    ]
    opt_dir = tmp_path / "cfg_opts2"
    configure_nasanic_types(
        opt_dir,
        opts2_sections,
        compact,
        {"dimensions": {"vi-sao-chon-chung-toi": {"width": 500, "height": 300}}},
        [],
    )
    static_php = (opt_dir / "type-static.php").read_text(encoding="utf-8")
    news_opts_php = (opt_dir / "type-news.php").read_text(encoding="utf-8")
    photo_opts_php = (opt_dir / "type-photo.php").read_text(encoding="utf-8")
    assert "'slideshow' =>" not in static_php
    assert "'slideshow' =>" in photo_opts_php
    assert photo_opts_php.index("'logo' =>") < photo_opts_php.index("'slideshow' =>")
    assert "'slide' =>" not in news_opts_php
    assert "'statistical' =>" in news_opts_php
    assert "'link-youtube' =>" in news_opts_php
    # 'vi-sao-chon-chung-toi' has no inner page in spec, >400px scales x1.2 (500x300 -> 600x360), no is_featured/slug/website
    assert "'width' => 600" in news_opts_php
    assert "'height' => 360" in news_opts_php
    assert "'is_featured'" not in news_opts_php.split("'video-clip'")[0]

    # Small icon non-inner-page type (e.g. 'tai-sao' 75x65) keeps 75x65x2 & minimal fields only
    why_sections = [
        SpecSectionItem(
            id="w1",
            order=1,
            name="Tại sao",
            scope="homepage",
            source="figma_and_spec",
            content_type="feature",
        )
    ]
    why_dir = tmp_path / "cfg_why"
    configure_nasanic_types(why_dir, why_sections, compact, {"dimensions": {"tai-sao": {"width": 75, "height": 65}}}, [])
    why_php = (why_dir / "type-news.php").read_text(encoding="utf-8")
    assert "'tai-sao' =>" in why_php
    assert "'thumb' => '75x65x2'" in why_php
    assert "'is_featured'" not in why_php
    assert "'website'" not in why_php
    assert "'slug'" not in why_php
    assert "'datePublish'" not in why_php

    # Verify per-section slogan/description static entry when spec asks for admin-editable description
    slogan_sections = [
        SpecSectionItem(
            id="sl0",
            order=0,
            name="Trang chủ",
            scope="menu",
            source="spec_only",
            content_type="article_single",
        ),
        SpecSectionItem(
            id="sl1",
            order=1,
            name="Sản phẩm nổi bật",
            scope="homepage",
            source="spec_only",
            content_type="product",
            spec_requirements="1. Mô tả chữ nhỏ góc phải cho nhập trong admin",
        )
    ]
    sl_dir = tmp_path / "cfg_slogan"
    sl_summary = configure_nasanic_types(sl_dir, slogan_sections, compact, {"dimensions": {}}, [])
    sl_static = (sl_dir / "type-static.php").read_text(encoding="utf-8")
    assert "'slogan-san-pham-noi-bat' =>" in sl_static
    assert "'lien-he' =>" in sl_static
    assert "'trang-chu' =>" not in sl_static
    assert any(i["key"] == "slogan-san-pham-noi-bat" for i in sl_summary["configured_types"])


def test_font_manager_google_local_woff2_convert_and_missing_report(
    tmp_path: Path, monkeypatch
) -> None:
    import asyncio
    from app.offline import font_manager as fm_mod

    # 1. Mock Google Fonts only succeeding for "Inter" via @import url(...), failing for others
    async def _fake_google(family: str):
        if family == "Inter":
            return {
                "family": "Inter",
                "source": "google_import",
                "files": [],
                "css": '@import url("https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,100..900;1,100..900&display=swap");',
            }
        return None

    monkeypatch.setattr(fm_mod, "_try_resolve_google_font_import", _fake_google)

    # 2. Local font dir has a .ttf that gets converted to .woff2 (no .ttf copied to output)
    local_pool = tmp_path / "FontPool"
    (local_pool / "MyCustomFont").mkdir(parents=True)
    (local_pool / "MyCustomFont" / "MyCustomFont-Bold.ttf").write_bytes(b"FAKE_TTF")

    def _fake_convert(src: Path, dst: Path) -> bool:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"WOF2_CONVERTED")
        return True

    monkeypatch.setattr(fm_mod, "_convert_to_woff2", _fake_convert)

    out_dir = tmp_path / "site"
    res = asyncio.run(
        fm_mod.resolve_and_install_fonts(
            ["Inter", "MyCustomFont", "UnknownMissingFont"],
            out_dir,
            font_source_dir=str(local_pool),
        )
    )

    assert res["missing_fonts"] == ["UnknownMissingFont"]
    installed_families = [f["family"] for f in res["installed_fonts"]]
    assert installed_families == ["Inter", "MyCustomFont"]
    # Only .woff/.woff2 allowed in output assets/fonts
    out_font_files = [p.name for p in (out_dir / "assets" / "fonts").rglob("*") if p.is_file()]
    assert all(name.endswith((".woff", ".woff2")) for name in out_font_files)
    assert "MyCustomFont-700.woff2" in out_font_files
    fonts_css = (out_dir / "assets" / "css" / "fonts.css").read_text(encoding="utf-8")
    assert '@import url("https://fonts.googleapis.com/css2?family=Inter' in fonts_css
    assert "MyCustomFont-700.woff2" in fonts_css
    assert ":root" not in fonts_css

    style_css_path = out_dir / "assets" / "css" / "style.css"
    fm_mod.upsert_root_fonts_in_style_css(style_css_path, res["main_font"], res["heading_font"])
    style_css = style_css_path.read_text(encoding="utf-8")
    assert "--font-main: 'Inter'" in style_css


def test_nasanic_seeder_skips_existing_types_and_seeds_empty_ones(
    tmp_path: Path, monkeypatch
) -> None:
    import pymysql
    from app.offline.nasanic_seeder import seed_nasanic_database

    (tmp_path / ".env").write_text(
        "DB_HOST=localhost\nDB_PORT=3306\nDB_DATABASE=test_db\nDB_USERNAME=root\nDB_PASSWORD=\nDB_PREFIX=table_\n",
        encoding="utf-8",
    )
    assets_dir = tmp_path / "assets"
    (assets_dir / "images").mkdir(parents=True)
    (assets_dir / "images" / "sample.webp").write_bytes(b"WEBP_DATA")

    inserted_rows = []

    class _FakeCursor:
        def __init__(self):
            self._last_result = None
            self.lastrowid = 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql: str, params=None):
            if sql.startswith("SHOW TABLES LIKE"):
                self._last_result = [(params[0],)]
            elif sql.startswith("SHOW COLUMNS FROM"):
                self._last_result = [
                    ("id",), ("type",), ("namevi",), ("slugvi",), ("descvi",),
                    ("contentvi",), ("photo",), ("numb",), ("is_show",), ("status",),
                    ("id_product",), ("id_news",), ("id_photo",), ("id_parent",),
                    ("com",), ("act",), ("model",), ("controller",), ("created_at",), ("updated_at",),
                ]
            elif sql.startswith("SELECT COUNT(*)"):
                # Pretend 'san-pham' already has 3 rows, 'tin-tuc' has 0 rows
                t_val = params[0] if params else ""
                self._last_result = [(3 if t_val == "san-pham" else 0,)]
            elif sql.startswith("INSERT INTO"):
                self.lastrowid += 1
                inserted_rows.append((sql, params))

        def fetchone(self):
            return self._last_result[0] if self._last_result else None

        def fetchall(self):
            return self._last_result or []

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(pymysql, "connect", lambda **kwargs: _FakeConn())

    cfg_summary = {
        "configured_types": [
            {"file": "config/type-products.php", "key": "san-pham", "category_levels": 1},
            {"file": "config/type-news.php", "key": "tin-tuc", "category_levels": 0},
        ]
    }
    res = seed_nasanic_database(
        tmp_path,
        "Demo Brand",
        cfg_summary,
        assets_dir,
        {"products": [{"title": "SP Demo", "desc": "Desc"}], "hero": {"subtitle": "Sub"}},
    )
    assert res["skipped_existing"] == [{"table": "table_product", "type": "san-pham", "existing": 3}]
    assert res["seeded"] == [{"table": "table_news", "type": "tin-tuc", "inserted": 4}]
    assert any("INSERT INTO `table_news`" in sql for sql, _ in inserted_rows)
    assert not any("INSERT INTO `table_product`" in sql for sql, _ in inserted_rows)


def test_wire_nasanic_controllers_injects_only_missing_queries(tmp_path: Path) -> None:
    from app.offline.nasanic_configurator import wire_nasanic_controllers

    ctrl_dir = tmp_path / "src" / "Controllers" / "Web"
    ctrl_dir.mkdir(parents=True)
    (ctrl_dir / "HomeController.php").write_text(
        "<?php\n"
        "            $about = StaticModel::where('type', 'gioi-thieu')->first();\n"
        "            $doitac = $homePhotos('doi-tac', 20);\n"
        "            $customer = $homeNews('y-kien-khach-hang', 12);\n"
        "            return get_defined_vars();\n",
        encoding="utf-8",
    )
    (ctrl_dir / "AllController.php").write_text(
        "<?php\nuse NASANICORE\\Models\\NewsModel;\n"
        "            $mapIframe = '';\n"
        "            foreach ($branches as $branch) {\n"
        "                if (!empty($branch['options2']['google_map'])) {\n"
        "                    $mapIframe = $branch['options2']['google_map'];\n"
        "                    break;\n"
        "                }\n"
        "            }\n"
        "            if (empty($mapIframe)) {\n"
        "                $mapIframe = $optSetting['coords_iframe'] ?? '';\n"
        "            }\n"
        "            return get_defined_vars();\n",
        encoding="utf-8",
    )

    cfg_summary = {
        "configured_types": [
            {"file": "config/type-static.php", "key": "gioi-thieu", "category_levels": 0},
            {"file": "config/type-products.php", "key": "menu", "category_levels": 2},
            {"file": "config/type-news.php", "key": "uu-dai", "category_levels": 1},
        ]
    }
    res = wire_nasanic_controllers(tmp_path, cfg_summary)
    assert set(res["updated_files"]) == {
        "src/Controllers/Web/HomeController.php",
        "src/Controllers/Web/AllController.php",
    }
    assert set(res["pruned_types"]) == {"doi-tac", "y-kien-khach-hang"}

    home_out = (ctrl_dir / "HomeController.php").read_text(encoding="utf-8")
    assert "$menu" in home_out
    assert "$uuDai" in home_out
    # 'gioi-thieu' already existed -> must not be duplicated
    assert home_out.count("$about") == 1
    # Unused queries pruned
    assert "doi-tac" not in home_out
    assert "y-kien-khach-hang" not in home_out

    all_out = (ctrl_dir / "AllController.php").read_text(encoding="utf-8")
    assert "$navMenu" in all_out
    assert "$navUuDai" in all_out
    assert "use NASANICORE\\Models\\NewsListModel;" in all_out
    assert "$branches" not in all_out
    assert "$mapIframe" not in all_out


def test_retry_and_delete_project_resets_state(tmp_path: Path, monkeypatch) -> None:
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
        req = ProjectCreate(
            name="Retry Delete Test",
            spec_text="1 | Giới thiệu | Một bài viết",
            figma_url="https://www.figma.com/design/DEMOKEY123/Test",
            target_source_dir=str(tmp_path),
            mode="demo",
        )
        state = await orch.create_and_start(req)
        await orch._tasks[state.id]
        assert state.phase == "waiting_plan_review"

        # Simulate a failed state
        state.phase = "failed"
        state.error_message = "Simulated error"
        local_bus.save_project(state)

        retried = await orch.retry_project(state.id)
        await orch._tasks[state.id]
        assert retried.phase == "waiting_plan_review"
        assert retried.error_message is None
        assert retried.plan_approved is False

        await orch.delete_project(state.id)
        assert local_bus.get_project(state.id) is None
        assert not (projects_root / state.id).exists()

    asyncio.run(_run())


def test_side_by_side_qc_banners_and_template_db_replacement_and_webp100(
    tmp_path: Path, monkeypatch
) -> None:
    import json as pyjson
    import pymysql
    from PIL import Image
    from app.offline.asset_pipeline import convert_workspace_images_to_webp
    from app.offline.figma_parser import extract_compact_tokens
    from app.offline.nasanic_seeder import build_figma_and_ai_seed_data, seed_nasanic_database

    fake_figma = {
        "name": "Co Khi Test",
        "document": {
            "id": "1:2",
            "name": "demo",
            "type": "CANVAS",
            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1920, "height": 5901},
            "fills": [{"type": "IMAGE", "visible": True}],
            "children": [
                {
                    "id": "4:289",
                    "name": "Quangcao",
                    "type": "GROUP",
                    "absoluteBoundingBox": {"x": 0, "y": 1215, "width": 1920, "height": 700},
                    "children": [],
                },
                {
                    "id": "4:356",
                    "name": "QC 1",
                    "type": "GROUP",
                    "absoluteBoundingBox": {"x": 310, "y": 2620, "width": 640, "height": 280},
                    "children": [],
                },
                {
                    "id": "4:382",
                    "name": "QC 2",
                    "type": "GROUP",
                    "absoluteBoundingBox": {"x": 970, "y": 2620, "width": 640, "height": 280},
                    "children": [],
                },
                {
                    "id": "5:436",
                    "name": "Thanhtuu",
                    "type": "GROUP",
                    "absoluteBoundingBox": {"x": 0, "y": 3630, "width": 1920, "height": 570},
                    "children": [
                        {
                            "id": "5:440",
                            "name": "stat",
                            "type": "TEXT",
                            "characters": "10+",
                            "absoluteBoundingBox": {"x": 100, "y": 3700, "width": 80, "height": 40},
                            "style": {"fontFamily": "Montserrat", "fontSize": 36, "fontWeight": 700},
                        },
                        {
                            "id": "5:441",
                            "name": "lbl",
                            "type": "TEXT",
                            "characters": "Năm kinh nghiệm cơ khí",
                            "absoluteBoundingBox": {"x": 100, "y": 3750, "width": 180, "height": 20},
                            "style": {"fontFamily": "Montserrat", "fontSize": 14, "fontWeight": 400},
                        },
                    ],
                },
            ],
        },
    }
    tok = extract_compact_tokens(fake_figma)
    sec_names = [s["name"] for s in tok["sections"]]
    assert "Quảng cáo" in sec_names
    assert "Quảng cáo 2" in sec_names
    qc2_sec = next(s for s in tok["sections"] if s["name"] == "Quảng cáo 2")
    assert qc2_sec["width"] == 640 and qc2_sec["height"] == 280 and qc2_sec["item_count"] == 2
    assert all(n["node_id"] != "1:2" for n in tok["export_nodes"])

    # Test convert_workspace_images_to_webp
    ws = tmp_path / "ws"
    (ws / "assets" / "images").mkdir(parents=True)
    (ws / "src" / "Views").mkdir(parents=True)
    Image.new("RGB", (20, 20), (10, 20, 30)).save(ws / "assets" / "images" / "bg-test.png")
    (ws / "src" / "Views" / "home.blade.php").write_text('<img src="assets/images/bg-test.png">', encoding="utf-8")
    conv = convert_workspace_images_to_webp(ws)
    assert "assets/images/bg-test.webp" in conv
    assert not (ws / "assets" / "images" / "bg-test.png").exists()
    assert "bg-test.webp" in (ws / "src" / "Views" / "home.blade.php").read_text(encoding="utf-8")

    # Test replace_template_data=True deletes old rows, formats upload path YYYY/MM/DD, seeds options2
    (ws / ".env").write_text(
        "DB_HOST=localhost\nDB_PORT=3306\nDB_DATABASE=test_db\nDB_USERNAME=root\nDB_PASSWORD=\nDB_PREFIX=table_\n",
        encoding="utf-8",
    )
    executed_sqls: list[str] = []
    inserted_rows: list[tuple[str, list]] = []

    class _MockCur:
        def __init__(self):
            self._res = []
            self.lastrowid = 10

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, sql: str, params=None):
            executed_sqls.append(sql)
            if sql.startswith("SHOW TABLES LIKE"):
                self._res = [(params[0],)]
            elif sql.startswith("SHOW COLUMNS FROM"):
                self._res = [
                    ("id",), ("type",), ("namevi",), ("slugvi",), ("descvi",),
                    ("contentvi",), ("photo",), ("numb",), ("options2",), ("options",),
                    ("addressvi",), ("is_show",), ("status",), ("id_news",), ("id_photo",),
                    ("id_parent",), ("com",), ("act",), ("model",), ("controller",),
                    ("created_at",), ("updated_at",),
                ]
            elif sql.startswith("SELECT COUNT(*)"):
                self._res = [(0,)]
            elif sql.startswith("SELECT id, options"):
                self._res = [(1, '{"hotline":"0909"}')]
            elif sql.startswith("INSERT INTO"):
                self.lastrowid += 1
                inserted_rows.append((sql, list(params or [])))

        def fetchone(self):
            return self._res[0] if self._res else None

        def fetchall(self):
            return self._res

    class _MockConn:
        def cursor(self):
            return _MockCur()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(pymysql, "connect", lambda **kw: _MockConn())
    cfg_sum = {
        "configured_types": [
            {
                "file": "config/type-news.php",
                "key": "thanh-tuu",
                "category_levels": 0,
                "options2_schema": {"statistical": {"type": "text", "title": "Số liệu"}},
                "has_inner_page": False,
            }
        ]
    }
    seed_payload = build_figma_and_ai_seed_data(tok, cfg_sum, "Cơ Khí", {"hero": {"subtitle": "Sub"}})
    res = seed_nasanic_database(
        ws, "Cơ Khí", cfg_sum, ws / "assets", seed_payload, replace_template_data=True
    )
    assert any(s.startswith("DELETE FROM `table_product`") for s in executed_sqls)
    news_inserts = [p for sql, p in inserted_rows if sql.startswith("INSERT INTO `table_news`")]
    assert news_inserts
    # Must contain upload folder + YYYY/MM/DD path and options2 JSON
    assert any(isinstance(v, str) and v.startswith("news/") and v.endswith(".webp") for row_p in news_inserts for v in row_p)
    assert any(isinstance(v, str) and '"statistical"' in v for row_p in news_inserts for v in row_p)


def test_leviet_5col_xlsx_and_vector_icons_and_unique_slug_seeding(
    tmp_path: Path, monkeypatch
) -> None:
    import pymysql
    from app.offline.figma_parser import extract_compact_tokens
    from app.offline.nasanic_configurator import configure_nasanic_types
    from app.offline.nasanic_seeder import build_figma_and_ai_seed_data, seed_nasanic_database
    from app.offline.spec_parser import parse_structured_spec

    # 1. 5-column xlsx spec rows (leading empty cell + numeric STT, plus double-STT row)
    spec_txt = (
        " | TÊN HỢP ĐỒNG | | CÔNG TY TNHH BÔNG SỢI LÊ VIỆT\n"
        " | 4 | MENU GIỚI THIỆU | 1. menu giới thiệu cho nhập 1 bài viết, hiển thị ngoài trang chủ | ok |\n"
        " | 5 | MENU SẢN PHẨM | Danh mục 2 cấp, check danh mục cấp 1 và sản phẩm nổi bật ra ngoài trang chủ, danh mục cấp 1 có icon | ok |\n"
        " | 6 | MENU DỊCH VỤ | Nhiều bài viết, lấy form theo tin tức ngoài trang chủ luôn không cần lấy dữ liệu mục dịch vụ | OK |\n"
        " | 7 | MENU TUYỂN DỤNG | 1 BÀI VIẾT | OK |\n"
        "7 | 8 | MENU TIN TỨC | Nhiều bài viết, nổi bật ra ngoài trang chủ | ok |\n"
        " | 11 | MỤC VÌ SAO CHỌN BÔNG SỢI LÊ VIỆT | Icon, tiêu đề và text | ok |\n"
        " | 12 | MỤC GÓC NHÌN NGÀNH DỆT MAY | Mục video, mỗi video nhập tiêu đề + mô tả + link youtube | ok |\n"
        " | 13 | GÓC NHÌN TỪ KHÁCH HÀNG | Không trang con, tiêu đề + địa chỉ + nội dung | ok |\n"
        " | 16 | BANNER CHO MENU | Mỗi menu có 1 banner kích thước 1300x400px | OK |\n"
    )
    parsed = parse_structured_spec(spec_txt)
    assert parsed["metadata"]["contract_name"] == "CÔNG TY TNHH BÔNG SỢI LÊ VIỆT"
    item_names = [i["name"] for i in parsed["items"]]
    assert "4" not in item_names and "7" not in item_names and "8" not in item_names
    by_name_scope = {(i["name"], i["scope"]): i for i in parsed["items"]}
    assert ("Tuyển Dụng", "menu") in by_name_scope
    assert by_name_scope[("Tuyển Dụng", "menu")]["content_type"] == "article_single"
    assert ("Sản Phẩm", "homepage") in by_name_scope
    assert ("Dịch Vụ", "homepage") not in by_name_scope  # explicitly said không cần lấy dữ liệu

    # 2. Figma extraction with page root frame + tall nhom_sp + vector icons + ::before bg separation
    figma_payload = {
        "nodes": {
            "6009:164": {
                "document": {
                    "id": "6009:164",
                    "name": "Trang chủ",
                    "type": "FRAME",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1920, "height": 6791},
                    "children": [
                        {
                            "id": "6009:278",
                            "name": "nhom_sp",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"x": 0, "y": 1490, "width": 1920, "height": 2407},
                            "children": [
                                {
                                    "id": "6009:284",
                                    "name": "bong",
                                    "type": "FRAME",
                                    "absoluteBoundingBox": {"x": 310, "y": 1600, "width": 1300, "height": 694},
                                    "children": [
                                        {
                                            "id": "6009:285",
                                            "name": "Bông",
                                            "type": "TEXT",
                                            "characters": "Bông",
                                            "absoluteBoundingBox": {"x": 360, "y": 1610, "width": 80, "height": 30},
                                            "style": {"fontFamily": "Montserrat", "fontSize": 24},
                                        },
                                        {
                                            "id": "6009:288",
                                            "name": "icon",
                                            "type": "GROUP",
                                            "absoluteBoundingBox": {"x": 310, "y": 1605, "width": 45, "height": 40},
                                            "children": [{"id": "6009:289", "type": "VECTOR"}],
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "id": "6009:354",
                            "name": "vi_sao",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"x": 0, "y": 3898, "width": 1920, "height": 548},
                            "children": [
                                {
                                    "id": "6009:355",
                                    "name": "::before",
                                    "type": "RECTANGLE",
                                    "absoluteBoundingBox": {"x": 0, "y": 3898, "width": 1920, "height": 548},
                                    "fills": [{"type": "IMAGE", "visible": True}],
                                },
                                {
                                    "id": "6009:361",
                                    "name": "Group 9",
                                    "type": "GROUP",
                                    "absoluteBoundingBox": {"x": 320, "y": 4050, "width": 54, "height": 49},
                                    "children": [{"id": "6009:362", "type": "VECTOR"}],
                                },
                            ],
                        },
                    ],
                }
            }
        }
    }
    tok = extract_compact_tokens(figma_payload)
    sec_names = [s["name"] for s in tok["sections"]]
    assert sec_names == ["nhom_sp", "vi_sao"]  # no sub-frame 'bong' leak & tall nhom_sp kept
    assert tok["sections"][0].get("sub_categories") == ["Bông"]
    roles = {(n["section"], n.get("role")) for n in tok["export_nodes"]}
    assert ("vi-sao", "section_bg") in roles
    assert ("vi-sao", "item_icon") in roles
    assert ("san-pham", "item_icon") in roles

    # 3. Configurator: homepage-only video has no website route; cam-nhan-khach-hang has address; tuyen-dung in type-static
    from app.models import SpecSectionItem
    cfg_dir = tmp_path / "cfg_leviet"
    secs_for_cfg = [
        SpecSectionItem(id="1", order=1, name="Tuyển dụng", scope="menu", source="spec_only", content_type="article_single"),
        SpecSectionItem(id="2", order=2, name="Sản phẩm", scope="homepage", source="figma_and_spec", content_type="product", category_levels=2, spec_requirements="Check danh mục cấp 1 và sản phẩm nổi bật ra ngoài trang chủ, icon"),
        SpecSectionItem(id="3", order=3, name="Video", scope="homepage", source="figma_and_spec", content_type="video", spec_requirements="link youtube"),
        SpecSectionItem(id="4", order=4, name="Cảm nhận khách hàng", scope="homepage", source="figma_and_spec", content_type="article_list", spec_requirements="không trang con, tiêu đề + địa chỉ + nội dung"),
    ]
    cfg_res = configure_nasanic_types(cfg_dir, secs_for_cfg, tok, {"dimensions": {}}, parsed["global_features"])
    static_out = (cfg_dir / "type-static.php").read_text(encoding="utf-8")
    news_out = (cfg_dir / "type-news.php").read_text(encoding="utf-8")
    prod_out = (cfg_dir / "type-products.php").read_text(encoding="utf-8")
    photo_out = (cfg_dir / "type-photo.php").read_text(encoding="utf-8")
    assert "'tuyen-dung' =>" in static_out
    assert "'video' =>" in news_out
    assert "'website'" not in news_out  # neither video (homepage-only) nor cam-nhan-khach-hang has inner route
    assert "'address' =>" in news_out
    assert "'icon' =>" in prod_out
    assert "'banner-tuyen-dung' =>" in photo_out

    # 4. Seeder deduplicates colliding slugs & seeds table_product_list_status
    ws = tmp_path / "ws_lv"
    (ws / "assets" / "images").mkdir(parents=True)
    (ws / ".env").write_text("DB_HOST=localhost\nDB_DATABASE=lv\nDB_PREFIX=table_\n", encoding="utf-8")
    from PIL import Image
    Image.new("RGB", (20, 20), (1, 2, 3)).save(ws / "assets" / "images" / "vi-sao-icon-1-g.webp", format="WEBP")
    Image.new("RGB", (20, 20), (4, 5, 6)).save(ws / "assets" / "images" / "bg-vi-sao-before.webp", format="WEBP")

    sql_log: list[tuple[str, list]] = []
    class _LVCur:
        def __init__(self): self._r = []; self.lastrowid = 0
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql: str, params=None):
            sql_log.append((sql, list(params or [])))
            if sql.startswith("SHOW TABLES LIKE"): self._r = [(params[0],)]
            elif sql.startswith("SHOW COLUMNS FROM"):
                # Omit photo2/icon on static/product_list to verify ALTER TABLE ... utf8mb4_general_ci auto-creation
                self._r = [(c,) for c in ("id","id_list","id_product_list","id_product","id_news","id_photo","id_parent","type","namevi","slugvi","descvi","contentvi","photo","numb","options2","is_show","status","com","act","model","controller","created_at","updated_at")]
            elif sql.startswith("SELECT COUNT(*)"): self._r = [(0,)]
            elif sql.startswith("SELECT id, options"): self._r = [(1, "{}")]
            elif sql.startswith("INSERT INTO"): self.lastrowid += 1
        def fetchone(self): return self._r[0] if self._r else None
        def fetchall(self): return self._r
    class _LVConn:
        def cursor(self): return _LVCur()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    monkeypatch.setattr(pymysql, "connect", lambda **kw: _LVConn())

    sd = build_figma_and_ai_seed_data(
        tok,
        cfg_res,
        "Lê Việt",
        {"hero": {"subtitle": "Sub"}},
        ai_seed_override={"section_items": {"cam-nhan-khach-hang": [{"name": "Khách A", "desc": "Tốt", "options2": {"address": "TP. HCM"}}, {"name": "Khách A", "desc": "Tốt 2"}]}},
        spec_metadata=parsed["metadata"],
    )
    seed_res = seed_nasanic_database(ws, "Lê Việt", cfg_res, ws / "assets", sd, replace_template_data=True)
    assert seed_res["warnings"] == []
    assert any(
        s.startswith("ALTER TABLE `table_product_list` ADD COLUMN `icon`")
        and "utf8mb4_general_ci" in s
        for s, _ in sql_log
    )
    assert any(s.startswith("INSERT INTO `table_product_list_status`") for s, _ in sql_log)
    slug_vals = [p[1] for s, p in sql_log if s.startswith("INSERT INTO `table_slug`")]
    assert len(slug_vals) == len(set(slug_vals))  # zero duplicate slugs!
