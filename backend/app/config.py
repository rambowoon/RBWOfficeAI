from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
ARTIFACTS_DIR = DATA_DIR / "artifacts"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


class Settings:
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8787"))
    FIGMA_ACCESS_TOKEN: str = os.getenv("FIGMA_ACCESS_TOKEN", "")
    DEFAULT_SOURCE_DIR: str = os.getenv(
        "DEFAULT_SOURCE_DIR", r"f:\RBWStudio\www\2026_11\source_nasani_29102026"
    )
    DEFAULT_PREVIEW_URL: str = os.getenv("DEFAULT_PREVIEW_URL", "")
    PHP_BIN: str = os.getenv("PHP_BIN", "")


settings = Settings()
