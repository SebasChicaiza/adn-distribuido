import argparse
from pathlib import Path
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor

def main():
    parser = argparse.ArgumentParser(description="Preprocess a FASTA file.")
    parser.add_argument("input_file", type=str, help="Path to input .fna file")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        return

    print(f"Preprocessing {input_path}...")
    norm_path, meta_path = FastaPreprocessor.preprocess(input_path)
    print(f"Success.\nNormalized sequence: {norm_path}\nMetadata: {meta_path}")

if __name__ == "__main__":
    main()
