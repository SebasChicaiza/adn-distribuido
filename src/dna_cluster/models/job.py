from pydantic import BaseModel, Field
from typing import Dict, List
from .chunk import ChunkInfo

class ChunkMetric(BaseModel):
    matches: int = 0
    evaluable_bases: int = 0
    unknown_bases: int = 0

class JobInfo(BaseModel):
    job_id: str
    input_a_hash: str
    input_b_hash: str
    total_chunks: int = 0
    chunks: Dict[str, ChunkInfo] = Field(default_factory=dict)
    chunk_metrics: Dict[str, ChunkMetric] = Field(default_factory=dict)
    matches_total: int = 0
    evaluable_bases_total: int = 0
    unknown_bases_total: int = 0
    state: str = "created" # created, running, completed, failed
