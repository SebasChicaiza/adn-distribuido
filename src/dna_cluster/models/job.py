from pydantic import BaseModel, Field
from typing import Dict, List
from .chunk import ChunkInfo

class JobInfo(BaseModel):
    job_id: str
    input_a_hash: str
    input_b_hash: str
    total_chunks: int = 0
    chunks: Dict[str, ChunkInfo] = Field(default_factory=dict)
    state: str = "created" # created, running, completed, failed
