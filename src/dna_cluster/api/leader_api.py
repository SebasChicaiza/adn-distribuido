from fastapi import APIRouter, HTTPException, Request
from dna_cluster.api.schemas import (
    RegisterRequest, ChunkUpdateRequest, JobCreateRequest, 
    WorkRequest, WorkResponse, ChunkResultRequest, StateSyncRequest
)
from dna_cluster.models.node import NodeInfo
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register")
async def register_node(req: RegisterRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    logger.info(f"Node registered: {req.node_info.node_id}")
    runtime.register_node(req.node_info)
    return {"status": "registered"}

@router.post("/heartbeat")
async def heartbeat(req: RegisterRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    runtime.update_node_heartbeat(req.node_info)
    return {"status": "ok"}

@router.post("/job/create")
async def create_job(req: JobCreateRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    try:
        runtime.create_job(req.job_id)
        return {"status": "job_created", "job_id": req.job_id}
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/chunk/request_work", response_model=WorkResponse)
async def request_work(req: WorkRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    work = runtime.request_work(req.node_id)
    if work:
        job_id, chunk = work
        return WorkResponse(
            has_work=True, 
            chunk_id=chunk.chunk_id, 
            job_id=job_id, 
            start_offset=chunk.start_offset, 
            length=chunk.length
        )
    return WorkResponse(has_work=False)

@router.post("/chunk/result")
async def chunk_result(req: ChunkResultRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    runtime.commit_chunk_result(req.chunk_id, req.job_id, req.result_data)
    return {"status": "ok"}

@router.post("/state/sync")
async def sync_state(req: StateSyncRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "receive_state_sync"):
        raise HTTPException(status_code=400, detail="Cannot receive state sync")
    runtime.receive_state_sync(req.state_json)
    return {"status": "synced"}
