from fastapi import APIRouter, HTTPException, Request
from dna_cluster.api.schemas import (
    RegisterRequest, ChunkUpdateRequest, JobCreateRequest, 
    WorkRequest, WorkResponse, ChunkResultRequest
)
from dna_cluster.models.node import NodeInfo
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register")
async def register_node(req: RegisterRequest, request: Request):
    logger.info(f"Node registered: {req.node_info.node_id}")
    runtime = request.app.state.runtime
    runtime.register_node(req.node_info)
    return {"status": "registered"}

@router.post("/heartbeat")
async def heartbeat(req: RegisterRequest, request: Request):
    runtime = request.app.state.runtime
    runtime.update_node_heartbeat(req.node_info)
    return {"status": "ok"}

@router.post("/job/create")
async def create_job(req: JobCreateRequest, request: Request):
    runtime = request.app.state.runtime
    try:
        runtime.create_job(req.job_id)
        return {"status": "job_created", "job_id": req.job_id}
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/chunk/request_work", response_model=WorkResponse)
async def request_work(req: WorkRequest, request: Request):
    runtime = request.app.state.runtime
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
    runtime.commit_chunk_result(req.chunk_id, req.job_id, req.result_data)
    return {"status": "ok"}

@router.post("/chunk/update")
async def update_chunk(req: ChunkUpdateRequest, request: Request):
    logger.info(f"Chunk update: {req.chunk_id} -> {req.state}")
    # Still available for tracking partial states like IN_PROGRESS
    return {"status": "ok"}
