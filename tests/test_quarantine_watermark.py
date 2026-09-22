from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import mempalace.backends.chroma as chroma


def _make_palace_db(path: Path) -> None:
    """Create a chromadb 1.5.x-shaped ``chroma.sqlite3`` with watermark rows."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE max_seq_id (segment_id TEXT PRIMARY KEY, seq_id BLOB NOT NULL)"
        )
        conn.execute(
            "INSERT INTO max_seq_id VALUES (?, ?)",
            ("3f1c4a2e-9b7d-4a3e-8c5f-1a2b3c4d5e6f", b"\x11\x11\x00\x00\x00\x01\x23"),
        )
        conn.execute(
            "INSERT INTO max_seq_id VALUES (?, ?)",
            ("ffffffff-0000-1111-2222-333344445555", b"\x11\x11\x00\x00\x00\x01\x24"),
        )
        conn.commit()
    finally:
        conn.close()


def _watermark_rows(path: Path) -> list[tuple[str, bytes]]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT segment_id, seq_id FROM max_seq_id").fetchall()
    finally:
        conn.close()


def test_clear_segment_watermark_deletes_only_target_row(tmp_path: Path) -> None:
    db_path = tmp_path / "chroma.sqlite3"
    _make_palace_db(db_path)

    chroma._clear_segment_watermark(str(db_path), "3f1c4a2e-9b7d-4a3e-8c5f-1a2b3c4d5e6f")

    remaining = _watermark_rows(db_path)
    assert remaining == [("ffffffff-0000-1111-2222-333344445555", b"\x11\x11\x00\x00\x00\x01\x24")]


def test_clear_segment_watermark_unknown_segment_is_noop(tmp_path: Path) -> None:
    db_path = tmp_path / "chroma.sqlite3"
    _make_palace_db(db_path)

    chroma._clear_segment_watermark(str(db_path), "no-such-segment")

    assert len(_watermark_rows(db_path)) == 2


def test_clear_segment_watermark_missing_table_is_silent(tmp_path: Path) -> None:
    db_path = tmp_path / "chroma.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    # Must not raise — older chromadb versions may lack the table entirely.
    chroma._clear_segment_watermark(str(db_path), "some-segment")
