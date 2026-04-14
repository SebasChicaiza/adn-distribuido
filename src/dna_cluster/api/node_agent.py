from fastapi import APIRouter, Request
from dna_cluster.api.schemas import HealthResponse, StatusResponse
from dna_cluster.config import settings
from dna_cluster.models.node import NodeInfo
from dna_cluster import __version__

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", node_id=settings.node_id, version=__version__)

@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request):
    runtime = getattr(request.app.state, "runtime", None)
    state = runtime.state if runtime else "starting"
    
    node_info = NodeInfo(
        node_id=settings.node_id,
        role_mode=settings.role_mode,
        leader_priority=settings.leader_priority,
        public_url=settings.public_url,
        state=state
    )
    return StatusResponse(node_info=node_info, gpu_available=False) # Phase 1 CPU only
