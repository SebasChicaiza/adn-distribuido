from pydantic import BaseModel
from typing import Optional

class ChunkState:
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    UPLOADED = "uploaded"
    COMMITTED = "committed"
    FAILED = "failed"
    RETRY = "retry"

class ChunkInfo(BaseModel):
    chunk_id: str
    job_id: str
    start_offset: int
    length: int
    state: str = ChunkState.PENDING
    assigned_node: Optional[str] = None
    result_hash: Optional[str] = None
