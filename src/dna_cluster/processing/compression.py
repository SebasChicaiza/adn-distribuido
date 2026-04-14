import gzip
from pathlib import Path

# Stub for Phase 2: Compression of chunk results before transmission
def compress_chunk_result(data: str, output_path: Path):
    with gzip.open(output_path, 'wt', encoding='utf-8') as f:
        f.write(data)

def decompress_chunk_result(input_path: Path) -> str:
    with gzip.open(input_path, 'rt', encoding='utf-8') as f:
        return f.read()
