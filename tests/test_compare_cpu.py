import pytest
from pathlib import Path
from dna_cluster.processing.compare_cpu import compare_chunks
from dna_cluster.processing.compare_gpu import compare_chunks as compare_chunks_gpu, get_backend_info

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


def test_compare_gpu_matches_cpu(tmp_path):
    """GPU/numpy module must produce identical results to the original CPU module."""
    file_a = tmp_path / "a.norm"
    file_b = tmp_path / "b.norm"

    file_a.write_bytes(b"ATCGAANnCGTACGT")
    file_b.write_bytes(b"ATTGAACCCGXACnT")

    for offset, length in [(0, 4), (4, 4), (0, 15), (8, 7)]:
        cpu = compare_chunks(file_a, file_b, offset, length)
        gpu = compare_chunks_gpu(file_a, file_b, offset, length)
        assert cpu == gpu, f"Mismatch at offset={offset}, len={length}: CPU={cpu} GPU={gpu}"


def test_gpu_backend_detected():
    backend, name = get_backend_info()
    assert backend in ("numpy", "cuda", "mps", "torch_cuda")
