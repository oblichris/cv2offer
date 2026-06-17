from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")


def unique_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    if not path.exists():
        return path
    return directory / f"{path.stem}_{uuid.uuid4().hex[:6]}{path.suffix}"


def write_markdown(directory: Path, filename: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = unique_path(directory, filename)
    path.write_text(content, encoding="utf-8")
    return path
