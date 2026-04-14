import pytest
from pathlib import Path
from dna_cluster.processing.compare_cpu import compare_chunks

def test_compare_cpu(tmp_path):
    file_a = tmp_path / "a.norm"
    file_b = tmp_path / "b.norm"

    file_a.write_text("ATCGAANNC")
    file_b.write_text("ATTGAACCC")

    # Range 0-4: ATCG vs ATTG -> ++.+
    res1 = compare_chunks(file_a, file_b, 0, 4)
    assert res1 == "++.+"

    # Range 4-8: AANN vs AACC -> ++NN
    res2 = compare_chunks(file_a, file_b, 4, 4)
    assert res2 == "++NN"
