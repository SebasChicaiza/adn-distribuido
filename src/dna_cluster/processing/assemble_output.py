from pathlib import Path
import json
from .layout import LayoutMetadata
from typing import Dict

def assemble_final_output(job_id: str, chunk_results_dir: Path, metadata_path: Path, output_path: Path):
    """
    Assembles chunk results using the layout metadata of file A.
    """
    with open(metadata_path, "r", encoding="utf-8") as fm:
        layout = LayoutMetadata(**json.load(fm))

    # Read all chunk results into a single string for Phase 1.
    # In Phase 2, we stream this.
    chunk_files = sorted(chunk_results_dir.glob(f"{job_id}_*.res"))
    flat_result = ""
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            flat_result += f.read()

    # Reconstruct
    with open(output_path, "w", encoding="utf-8") as fout:
        result_offset = 0
        header_idx = 0
        line_idx = 0

        # Assuming headers are interleaved based on their original sequence offset
        while result_offset < len(flat_result) or header_idx < len(layout.headers):
            # Write pending headers for this offset
            while header_idx < len(layout.headers) and layout.headers[header_idx]["offset"] <= result_offset:
                fout.write(layout.headers[header_idx]["text"] + "\n")
                header_idx += 1

            if line_idx < len(layout.line_lengths):
                length = layout.line_lengths[line_idx]
                fout.write(flat_result[result_offset:result_offset+length] + "\n")
                result_offset += length
                line_idx += 1
            else:
                break
