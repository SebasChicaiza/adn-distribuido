from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from .node import NodeInfo

from .job import JobInfo

class ClusterState(BaseModel):
    term: int = 0
    leader_id: Optional[str] = None
    nodes: Dict[str, NodeInfo] = Field(default_factory=dict)
    known_nodes: List[str] = Field(default_factory=list)
    active_jobs: Dict[str, JobInfo] = Field(default_factory=dict)
