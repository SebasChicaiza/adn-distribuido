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
    
    if runtime and hasattr(runtime, "is_leader"):
        # This is a LeaderRuntime acting as both
        state = "ready" # If it's acting as leader it's usually ready
        is_leader = runtime.is_leader
        term = runtime.state.term
    elif runtime:
        # This is a NodeRuntime
        state = runtime.state if runtime else "starting"
        is_leader = False
        term = runtime.current_term
    else:
        state = "offline"
        is_leader = False
        term = 0
        
    node_info = NodeInfo(
        node_id=settings.node_id,
        role_mode=settings.role_mode,
        leader_priority=settings.my_priority,
        public_url=settings.public_url,
        state=state,
        term=term
    )
    return StatusResponse(node_info=node_info, gpu_available=False, is_leader=is_leader, term=term)

@router.get("/activity")
async def get_activity(request: Request):
    """Shows what this node is currently doing — chunks being processed, cache stats."""
    runtime = getattr(request.app.state, "runtime", None)
    if not runtime:
        return {"node_id": settings.node_id, "state": "offline"}

    active = dict(runtime._active_chunks) if hasattr(runtime, "_active_chunks") else {}
    max_conc = runtime._max_concurrent if hasattr(runtime, "_max_concurrent") else 1
    cached = runtime.get_cached_chunks() if hasattr(runtime, "get_cached_chunks") else {}

    return {
        "node_id": settings.node_id,
        "is_leader": getattr(runtime, "is_leader", False),
        "max_concurrent_chunks": max_conc,
        "active_chunks": active,
        "active_count": len(active),
        "cached_chunks": {k: len(v) for k, v in cached.items()},
    }

@router.get("/chunk_cache/list")
async def list_cached_chunks(request: Request):
    """List all locally cached chunk results (for failover recovery)."""
    runtime = getattr(request.app.state, "runtime", None)
    if not runtime or not hasattr(runtime, "get_cached_chunks"):
        return {"cached_chunks": {}}
    return {"cached_chunks": runtime.get_cached_chunks()}

@router.get("/chunk_cache/get")
async def get_cached_chunk(job_id: str, chunk_id: str, request: Request):
    """Retrieve a single cached chunk result (for new leader recovery)."""
    runtime = getattr(request.app.state, "runtime", None)
    if not runtime or not hasattr(runtime, "get_cached_chunk_data"):
        return {"result_data": None}
    data = runtime.get_cached_chunk_data(job_id, chunk_id)
    return {"result_data": data}
