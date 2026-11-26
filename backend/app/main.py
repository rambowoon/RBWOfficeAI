from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agents.orchestrator import OfficeOrchestrator
from .agents.sdk_adapter import check_sdk_status
from .config import ARTIFACTS_DIR, PROJECTS_DIR, get_runtime_env, settings
from .event_bus import EventBus
from .models import AgentChatRequest, BugReviewRequest, PlanApprovalRequest, ProjectCreate
from .offline.spec_parser import parse_spec_upload, parse_structured_spec

bus = EventBus()
orchestrator = OfficeOrchestrator(bus=bus)

app = FastAPI(title="RBWOfficeAI — Web Automation Studio", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")
app.mount("/preview-sandbox", StaticFiles(directory=str(PROJECTS_DIR)), name="preview-sandbox")


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "sdk": check_sdk_status(),
        "figma_token_configured": bool(get_runtime_env("FIGMA_ACCESS_TOKEN")),
        "playwright_ready": True,
        "default_source_dir": settings.DEFAULT_SOURCE_DIR,
    }


@app.get("/api/projects")
async def list_projects() -> list[dict]:
    return [p.model_dump(mode="json") for p in bus.list_projects()]


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    project = bus.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump(mode="json")


@app.post("/api/specs/parse")
async def parse_spec_file(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="File rỗng")
    try:
        text = parse_spec_upload(file.filename or "", raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Không đọc được file: {exc}")
    return {
        "filename": file.filename,
        "text": text,
        "structured": parse_structured_spec(text),
    }


def _open_folder_dialog() -> str:
    """Open native Windows folder picker dialog and return normalized path (or empty string)."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(title="Chọn thư mục Source gốc")
    finally:
        root.destroy()
    return os.path.normpath(selected) if selected else ""


@app.post("/api/workspace/pick-folder")
async def pick_workspace_folder() -> dict:
    try:
        selected = await asyncio.to_thread(_open_folder_dialog)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không mở được hộp thoại chọn thư mục: {exc}")
    return {"path": selected, "cancelled": not bool(selected)}


@app.post("/api/projects", status_code=201)
async def create_project(req: ProjectCreate) -> dict:
    if req.mode == "live_sdk" and not req.target_source_dir.strip():
        raise HTTPException(
            status_code=400,
            detail="Vui lòng chọn Source dự án trước khi chạy chế độ Live SDK.",
        )
    state = await orchestrator.create_and_start(req)
    return state.model_dump(mode="json")


@app.post("/api/projects/{project_id}/retry")
async def retry_project(project_id: str) -> dict:
    try:
        state = await orchestrator.retry_project(project_id)
        return state.model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    try:
        await orchestrator.delete_project(project_id)
        return {"ok": True, "deleted": project_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.post("/api/projects/{project_id}/plan/approve")
async def approve_plan(project_id: str, req: PlanApprovalRequest) -> dict:
    try:
        state = await orchestrator.approve_leader_plan(project_id, req)
        return state.model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/projects/{project_id}/bugs/review")
async def review_bugs(project_id: str, req: BugReviewRequest) -> dict:
    try:
        state = await orchestrator.submit_bug_review(project_id, req)
        return state.model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/projects/{project_id}/agents/{agent_id}/chat")
async def chat_with_agent(
    project_id: str, agent_id: str, req: AgentChatRequest
) -> dict:
    try:
        agent = await orchestrator.send_agent_chat(project_id, agent_id, req.message)
        return agent.model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/projects/{project_id}/tokens")
async def get_project_tokens(project_id: str) -> JSONResponse:
    tokens_path = Path(PROJECTS_DIR / project_id / "tokens.json")
    if not tokens_path.exists():
        raise HTTPException(status_code=404, detail="tokens.json not ready yet")
    return JSONResponse(json.loads(tokens_path.read_text(encoding="utf-8")))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await bus.register_ws(ws)
    try:
        while True:
            # Keep connection alive; ignore ping frames/messages from client
            await ws.receive_text()
    except WebSocketDisconnect:
        await bus.unregister_ws(ws)
    except Exception:
        await bus.unregister_ws(ws)
