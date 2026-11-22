from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from .config import PROJECTS_DIR
from .models import ProjectState, utc_now_iso


class EventBus:
    """Manages persistent project state on disk and real-time WebSocket broadcasts."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._projects: dict[str, ProjectState] = {}
        self._lock = asyncio.Lock()
        self._load_existing_projects()

    def _state_path(self, project_id: str) -> Path:
        p_dir = PROJECTS_DIR / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir / "state.json"

    def _load_existing_projects(self) -> None:
        if not PROJECTS_DIR.exists():
            return
        for state_file in PROJECTS_DIR.glob("*/state.json"):
            try:
                raw = json.loads(state_file.read_text(encoding="utf-8"))
                state = ProjectState.model_validate(raw)
                self._projects[state.id] = state
            except Exception:
                continue

    def list_projects(self) -> list[ProjectState]:
        return sorted(
            self._projects.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )

    def get_project(self, project_id: str) -> ProjectState | None:
        return self._projects.get(project_id)

    def save_project(self, state: ProjectState) -> None:
        state.updated_at = utc_now_iso()
        self._projects[state.id] = state
        # ProjectState intentionally has no figma_token field, guaranteeing secrets never hit disk.
        self._state_path(state.id).write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    async def register_ws(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        snapshot = {
            "type": "snapshot",
            "project_id": None,
            "timestamp": utc_now_iso(),
            "payload": {
                "projects": [p.model_dump(mode="json") for p in self.list_projects()]
            },
        }
        await ws.send_json(snapshot)

    async def unregister_ws(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def emit(
        self,
        event_type: str,
        project_id: str,
        payload: dict[str, Any] | None = None,
        persist_state: ProjectState | None = None,
    ) -> None:
        if persist_state is not None:
            self.save_project(persist_state)

        envelope = {
            "type": event_type,
            "project_id": project_id,
            "timestamp": utc_now_iso(),
            "payload": payload or {},
        }
        async with self._lock:
            targets = list(self._connections)

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(envelope)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    async def emit_project_sync(self, state: ProjectState, reason: str = "state_sync") -> None:
        await self.emit(
            "project_sync",
            state.id,
            {"reason": reason, "project": state.model_dump(mode="json")},
            persist_state=state,
        )
