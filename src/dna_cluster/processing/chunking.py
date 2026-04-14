from pathlib import Path
import math
from typing import List
from dna_cluster.models.chunk import ChunkInfo
from dna_cluster.config import settings

def chunk_file(normalized_path: Path, job_id: str, chunk_size: int = None) -> List[ChunkInfo]:
    file_size = normalized_path.stat().st_size
    if chunk_size is None:
        chunk_size = settings.chunk_size_bytes
    num_chunks = math.ceil(file_size / chunk_size) if file_size > 0 else 0
    
    chunks = []
    for i in range(num_chunks):
        start_offset = i * chunk_size
        length = min(chunk_size, file_size - start_offset)
        chunks.append(ChunkInfo(
            chunk_id=f"{job_id}_{i}",
            job_id=job_id,
            start_offset=start_offset,
            length=length
        ))
    return chunks
