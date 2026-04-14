import pytest
from pathlib import Path
from dna_cluster.processing.chunking import chunk_file

def test_chunking(tmp_path, monkeypatch):
    # Mock chunk size
    from dna_cluster.config import settings
    monkeypatch.setattr(settings, "chunk_size_bytes", 4)

    norm_file = tmp_path / "test.norm"
    norm_file.write_text("ATCGNNAA") # 8 bytes -> 2 chunks

    chunks = chunk_file(norm_file, "job1")
    assert len(chunks) == 2
    assert chunks[0].start_offset == 0
    assert chunks[0].length == 4
    assert chunks[1].start_offset == 4
    assert chunks[1].length == 4
