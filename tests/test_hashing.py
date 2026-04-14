import pytest
from pathlib import Path
from dna_cluster.processing.hashing import get_file_hash

def test_get_file_hash(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("hello world")
    
    # sha256 of 'hello world'
    expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert get_file_hash(p) == expected
