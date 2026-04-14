import argparse
from pathlib import Path
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor
from dna_cluster.processing.chunking import chunk_file
from dna_cluster.processing.compare_cpu import compare_chunks
from dna_cluster.processing.assemble_output import assemble_final_output
from dna_cluster.storage.paths import StoragePaths
from dna_cluster.utils.ids import generate_job_id
import shutil

def main():
    parser = argparse.ArgumentParser(description="Run a full local comparison.")
    parser.add_argument("file_a", type=str, help="Path to first .fna")
    parser.add_argument("file_b", type=str, help="Path to second .fna")
    args = parser.parse_args()

    path_a = Path(args.file_a)
    path_b = Path(args.file_b)

    print("1. Preprocessing inputs...")
    norm_a, meta_a = FastaPreprocessor.preprocess(path_a)
    norm_b, meta_b = FastaPreprocessor.preprocess(path_b)

    job_id = generate_job_id()
    print(f"2. Chunking... (Job ID: {job_id})")
    chunks = chunk_file(norm_a, job_id)
    
    # Ensure work dir exists
    work_dir = StoragePaths.get_work_dir() / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    print("3. Comparing chunks (CPU)...")
    for chunk in chunks:
        res = compare_chunks(norm_a, norm_b, chunk.start_offset, chunk.length)
        chunk_res_path = work_dir / f"{chunk.chunk_id}.res"
        with open(chunk_res_path, "w", encoding="utf-8") as f:
            f.write(res)
        print(f"  Processed {chunk.chunk_id}")

    print("4. Assembling output...")
    output_path = StoragePaths.get_output_dir() / f"result_{job_id}.fna"
    assemble_final_output(job_id, work_dir, meta_a, output_path)

    print(f"\nDone! Final output saved to: {output_path}")

if __name__ == "__main__":
    main()
