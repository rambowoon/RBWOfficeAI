from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

try:
    import google.antigravity as ga  # type: ignore

    SDK_AVAILABLE = True
    SDK_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - environment dependent
    ga = None
    SDK_AVAILABLE = False
    SDK_IMPORT_ERROR = str(exc)


def check_sdk_status() -> dict[str, Any]:
    if SDK_AVAILABLE:
        return {"available": True, "detail": "google-antigravity SDK ready"}
    return {"available": False, "detail": SDK_IMPORT_ERROR or "google-antigravity not installed"}


class AntigravityAgentRunner:
    """Thin async adapter over the Antigravity Python SDK."""

    async def run_task(
        self,
        *,
        system_instructions: str,
        prompt: str,
        working_dir: str | None = None,
        skills_dir: str | None = None,
        on_thought: Callable[[str], Awaitable[None]] | None = None,
        on_tool_call: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        if not SDK_AVAILABLE or ga is None:
            raise RuntimeError(f"Antigravity SDK unavailable: {SDK_IMPORT_ERROR}")

        workspaces = [working_dir] if working_dir and Path(working_dir).exists() else None
        skills_paths = [skills_dir] if skills_dir and Path(skills_dir).exists() else None

        config = ga.LocalAgentConfig(
            system_instructions=system_instructions,
            capabilities=ga.CapabilitiesConfig(),
            workspaces=workspaces,
            skills_paths=skills_paths,
        )

        collected_text: list[str] = []
        async with ga.Agent(config) as agent:
            response = await agent.chat(prompt)

            async def _read_thoughts() -> None:
                async for thought in response.thoughts:
                    if thought and on_thought:
                        await on_thought(thought)

            async def _read_tool_calls() -> None:
                async for call in response.tool_calls:
                    if not on_tool_call:
                        continue
                    raw_name = getattr(call, "name", "tool")
                    tool_name = (
                        raw_name.value if hasattr(raw_name, "value") else str(raw_name)
                    )
                    await on_tool_call(
                        {
                            "name": tool_name,
                            "args": getattr(call, "args", {}) or {},
                            "kind": "ai_tool",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

            async def _read_tokens() -> None:
                async for delta in response:
                    if delta:
                        collected_text.append(str(delta))

            await asyncio.gather(_read_thoughts(), _read_tool_calls(), _read_tokens())

        return "".join(collected_text).strip()
