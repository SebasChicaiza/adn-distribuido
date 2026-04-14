from pydantic import BaseModel
from typing import Optional, List
from dna_cluster.models.node import NodeInfo

class HealthResponse(BaseModel):
    status: str
    node_id: str
    version: str

class StatusResponse(BaseModel):
    node_info: NodeInfo
    gpu_available: bool = False

class RegisterRequest(BaseModel):
    node_info: NodeInfo

class JobCreateRequest(BaseModel):
    job_id: str

class WorkRequest(BaseModel):
    node_id: str

class WorkResponse(BaseModel):
    has_work: bool
    chunk_id: Optional[str] = None
    job_id: Optional[str] = None
    start_offset: Optional[int] = None
    length: Optional[int] = None

class ChunkResultRequest(BaseModel):
    node_id: str
    chunk_id: str
    job_id: str
    result_data: str

class ChunkUpdateRequest(BaseModel):
    chunk_id: str
    state: str
    result_hash: Optional[str] = None
