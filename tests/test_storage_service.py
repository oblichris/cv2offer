from __future__ import annotations

from pathlib import Path

from server.services.storage_service import timestamp, unique_path, write_markdown


def test_timestamp_is_second_precision_string():
    value = timestamp()

    assert len(value) == 15
    assert value[8] == "_"


def test_write_markdown_creates_file(tmp_path: Path):
    path = write_markdown(tmp_path, "report.md", "# Hello")

    assert path.read_text(encoding="utf-8") == "# Hello"
    assert path.name == "report.md"


def test_write_markdown_does_not_overwrite_existing_file(tmp_path: Path):
    first = write_markdown(tmp_path, "report.md", "first content")
    second = write_markdown(tmp_path, "report.md", "second content")

    assert first.exists()
    assert second.exists()
    assert first != second
    assert first.read_text(encoding="utf-8") == "first content"
    assert second.read_text(encoding="utf-8") == "second content"


def test_unique_path_returns_original_when_absent(tmp_path: Path):
    path = unique_path(tmp_path, "new.md")

    assert path == tmp_path / "new.md"


def test_unique_path_returns_different_path_when_present(tmp_path: Path):
    existing = tmp_path / "report.md"
    existing.write_text("keep", encoding="utf-8")

    path = unique_path(tmp_path, "report.md")

    assert path != existing
    assert path.stem.startswith("report")
    assert path.suffix == ".md"
