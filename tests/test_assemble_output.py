import pytest
import json
from pathlib import Path
from dna_cluster.processing.assemble_output import assemble_final_output
from dna_cluster.processing.layout import LayoutMetadata

def test_assemble_output(tmp_path):
    job_id = "testjob"
    
    # Create metadata
    meta_path = tmp_path / "meta.json"
    layout = LayoutMetadata(
        headers=[{"offset": 0, "text": ">seq1"}, {"offset": 4, "text": ">seq2"}],
        line_lengths=[4, 4]
    )
    with open(meta_path, "w") as f:
        f.write(layout.model_dump_json())

    # Create chunk results
    chunk_dir = tmp_path / "work"
    chunk_dir.mkdir()
    (chunk_dir / f"{job_id}_0.res").write_text("++.+")
    (chunk_dir / f"{job_id}_1.res").write_text("++NN")

    output_path = tmp_path / "output.fna"

    assemble_final_output(job_id, chunk_dir, meta_path, output_path)

    expected = ">seq1\n++.+\n>seq2\n++NN\n"
    assert output_path.read_text() == expected
