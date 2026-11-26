from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..config import get_runtime_env


def _find_agy_cli() -> str | None:
    """Locate the Antigravity CLI (`agy` / `agy.exe`) binary on the local machine."""
    override = get_runtime_env("AGY_CLI_PATH")
    if override and Path(override).is_file():
        return override

    which_hit = shutil.which("agy") or shutil.which("agy.exe")
    if which_hit:
        return which_hit

    for candidate in (
        Path.home() / ".gemini" / "bin" / "agy.exe",
        Path.home() / ".gemini" / "bin" / "agy",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def check_sdk_status() -> dict[str, Any]:
    agy_path = _find_agy_cli()
    if agy_path:
        return {
            "available": True,
            "detail": f"Antigravity CLI ready ({Path(agy_path).name})",
            "backend": "cli",
        }
    return {
        "available": False,
        "detail": "Không tìm thấy Antigravity CLI (agy.exe). Hãy cài đặt agy hoặc cấu hình AGY_CLI_PATH trong backend/.env.",
    }


class AntigravityAgentRunner:
    """Executes agent tasks exclusively via Antigravity CLI (`agy` / `agy.exe`)."""

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
        agy_path = _find_agy_cli()
        if not agy_path:
            raise RuntimeError(
                "Không tìm thấy Antigravity CLI (agy.exe). Vui lòng cài đặt agy CLI hoặc cấu hình AGY_CLI_PATH trong backend/.env."
            )

        sections = [
            "=== SYSTEM INSTRUCTIONS ===",
            system_instructions.strip(),
        ]
        if skills_dir and Path(skills_dir).exists():
            sections.append(f"Skills directory: {skills_dir}")
        sections.extend(["", "=== TASK ===", prompt.strip()])
        combined_prompt = "\n".join(sections)

        temp_prompt_file: Path | None = None
        prompt_arg = combined_prompt
        # Keep well under Windows CreateProcess 32,767 char limit
        if len(combined_prompt) > 22000:
            fd, tmp_name = tempfile.mkstemp(prefix="rbw_prompt_", suffix=".txt")
            os.close(fd)
            temp_prompt_file = Path(tmp_name)
            temp_prompt_file.write_text(combined_prompt, encoding="utf-8")
            prompt_arg = (
                f"Đọc toàn bộ hướng dẫn và yêu cầu trong file `{temp_prompt_file}` "
                f"rồi thực hiện chính xác theo yêu cầu đó."
            )

        args = [
            agy_path,
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
        ]
        model_override = get_runtime_env("AGY_CLI_MODEL")
        if model_override:
            args.extend(["--model", model_override])

        cwd: str | None = None
        temp_cwd_obj: tempfile.TemporaryDirectory[str] | None = None
        if working_dir and Path(working_dir).exists():
            cwd = working_dir
            args.extend(["--add-dir", working_dir])
        else:
            # Pure analysis step: run in an empty isolated temp folder with slash commands disabled
            temp_cwd_obj = tempfile.TemporaryDirectory(prefix="rbw_agy_cwd_")
            cwd = temp_cwd_obj.name
            args.append("--disable-slash-commands")

        args.append(f"-p={prompt_arg}")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )

        def _reader_worker() -> None:
            try:
                assert proc.stdout is not None
                for raw_line in iter(proc.stdout.readline, b""):
                    loop.call_soon_threadsafe(queue.put_nowait, ("line", raw_line))
                err_bytes = proc.stderr.read() if proc.stderr else b""
                rc = proc.wait()
                loop.call_soon_threadsafe(queue.put_nowait, ("done", (rc, err_bytes)))
            except Exception as exc:  # pragma: no cover
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))

        reader = threading.Thread(target=_reader_worker, daemon=True)
        reader.start()

        collected_deltas: list[str] = []
        seen_tool_steps: set[int] = set()
        final_response: str | None = None
        error_msg: str | None = None
        rc = 0
        stderr_bytes = b""

        try:
            while True:
                kind, payload = await queue.get()
                if kind == "error":
                    raise payload
                if kind == "done":
                    rc, stderr_bytes = payload
                    break

                line = payload.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ev_type = evt.get("event")
                if ev_type == "step_update":
                    su = evt.get("step_update") or {}
                    step_type = str(su.get("step_type") or "")
                    text_delta = su.get("text_delta")
                    if text_delta and "agent_response" in step_type:
                        collected_deltas.append(str(text_delta))
                    elif text_delta and ("thought" in step_type or "thinking" in step_type):
                        if on_thought:
                            await on_thought(str(text_delta))
                    if su.get("thought") and on_thought:
                        await on_thought(str(su["thought"]))

                    tool_info = (
                        su.get("tool_info")
                        if isinstance(su.get("tool_info"), dict)
                        else {}
                    )
                    tool_call_obj = (
                        su.get("tool_call")
                        if isinstance(su.get("tool_call"), dict)
                        else {}
                    )
                    tool_name = (
                        su.get("tool_name")
                        or tool_info.get("name")
                        or tool_call_obj.get("name")
                    )
                    if tool_name and on_tool_call:
                        step_idx = su.get("step_index")
                        step_state = str(su.get("state") or "")
                        if (
                            step_idx is not None
                            and step_state == "DONE"
                            and step_idx in seen_tool_steps
                        ):
                            continue
                        if step_idx is not None:
                            seen_tool_steps.add(step_idx)
                        tool_args = (
                            tool_info.get("parameters")
                            or su.get("tool_args")
                            or su.get("args")
                            or su.get("input")
                            or tool_call_obj.get("args")
                            or {}
                        )
                        await on_tool_call(
                            {
                                "name": str(tool_name),
                                "args": tool_args,
                                "kind": "ai_tool",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                elif ev_type == "result":
                    res = evt.get("result") or {}
                    status = str(res.get("status") or "").upper()
                    if status and status != "SUCCESS":
                        error_msg = str(res.get("error") or f"Antigravity CLI status={status}")
                    if isinstance(res.get("response"), str) and res["response"].strip():
                        final_response = res["response"].strip()
        finally:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            if temp_prompt_file and temp_prompt_file.exists():
                try:
                    temp_prompt_file.unlink()
                except OSError:
                    pass
            if temp_cwd_obj is not None:
                try:
                    temp_cwd_obj.cleanup()
                except OSError:
                    pass

        if error_msg:
            raise RuntimeError(error_msg)
        if rc != 0 and not final_response and not collected_deltas:
            err_txt = stderr_bytes.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"Antigravity CLI exited ({rc}): {err_txt or 'unknown error'}")

        if final_response:
            return final_response
        return "".join(collected_deltas).strip()
