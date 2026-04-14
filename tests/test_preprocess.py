import pytest
import json
from pathlib import Path
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor

def test_preprocess(tmp_path, monkeypatch):
    # Mock settings data_dir
    from dna_cluster.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    fna_content = ">seq1\nATCG\n>seq2\nNNAA\n"
    input_file = tmp_path / "test.fna"
    input_file.write_text(fna_content)

    norm_path, meta_path = FastaPreprocessor.preprocess(input_file)
    
    assert norm_path.exists()
    assert meta_path.exists()
    
    assert norm_path.read_text() == "ATCGNNAA"
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    assert len(meta["headers"]) == 2
    assert meta["headers"][0] == {"offset": 0, "text": ">seq1"}
    assert meta["headers"][1] == {"offset": 4, "text": ">seq2"}
    assert meta["line_lengths"] == [4, 4]
