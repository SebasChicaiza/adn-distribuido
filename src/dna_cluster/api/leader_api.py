from fastapi import APIRouter, HTTPException, Request
from dna_cluster.api.schemas import (
    RegisterRequest, ChunkUpdateRequest, JobCreateRequest, 
    WorkRequest, WorkResponse, ChunkResultRequest, StateSyncRequest,
    SetPriorityRequest, SetSchedulerModeRequest
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

@router.get("/control/status")
async def control_status(request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    
    now = __import__("time").time()
    nodes_summary = {}
    for node_id, node in runtime.state.nodes.items():
        nodes_summary[node_id] = {
            "state": node.state,
            "is_disabled": node.is_disabled,
            "leader_priority": node.leader_priority,
            "available_ram_gb": round(node.available_ram_bytes / (1024**3), 2) if node.available_ram_bytes else 0,
            "total_ram_gb": round(node.total_ram_bytes / (1024**3), 2) if node.total_ram_bytes else 0,
            "cpu_count": node.cpu_count,
            "cpu_load_percent": node.cpu_load_percent,
            "disk_free_gb": round(node.disk_free_bytes / (1024**3), 2) if node.disk_free_bytes else 0,
            "last_seen_ago_s": round(now - node.last_seen_at, 1) if node.last_seen_at else None,
            "public_url": node.public_url,
        }
    
    jobs_summary = {}
    for job_id, job in runtime.state.active_jobs.items():
        total = len(job.chunks)
        committed = sum(1 for c in job.chunks.values() if c.state == "committed")
        pending = sum(1 for c in job.chunks.values() if c.state in ("pending", "retry"))
        assigned = sum(1 for c in job.chunks.values() if c.state in ("assigned", "in_progress"))
        jobs_summary[job_id] = {
            "state": job.state,
            "total_chunks": total,
            "committed": committed,
            "pending": pending,
            "in_progress": assigned,
            "progress_pct": round(committed / total * 100, 1) if total else 0,
        }
    
    return {
        "leader": runtime.state.leader_id,
        "term": runtime.state.term,
        "scheduler_mode": runtime.state.scheduler_mode, 
        "pinned_node_id": runtime.state.pinned_node_id,
        "active_nodes": len([n for n in runtime.state.nodes.values() if (now - n.last_seen_at < 60)]),
        "nodes": nodes_summary,
        "jobs": jobs_summary,
    }

@router.post("/control/disable_node")
async def disable_node(req: WorkRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    node = runtime.state.nodes.get(req.node_id)
    if node:
        node.is_disabled = True
        runtime.store.save(runtime.state)
        return {"status": "ok", "node": node.node_id, "is_disabled": True}
    raise HTTPException(status_code=404, detail="Node not found")

@router.post("/control/enable_node")
async def enable_node(req: WorkRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    node = runtime.state.nodes.get(req.node_id)
    if node:
        node.is_disabled = False
        runtime.store.save(runtime.state)
        return {"status": "ok", "node": node.node_id, "is_disabled": False}
    raise HTTPException(status_code=404, detail="Node not found")

@router.post("/control/set_scheduler_mode")
async def set_scheduler_mode(req: SetSchedulerModeRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    runtime.state.scheduler_mode = req.mode
    if req.pinned_node_id:
        runtime.state.pinned_node_id = req.pinned_node_id
    runtime.store.save(runtime.state)
    return {"status": "ok", "mode": req.mode}

@router.post("/control/set_priority")
async def set_priority(req: SetPriorityRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    node = runtime.state.nodes.get(req.node_id)
    if node:
        node.leader_priority = req.priority
        runtime.store.save(runtime.state)
        return {"status": "ok", "node": node.node_id, "priority": req.priority}
    raise HTTPException(status_code=404, detail="Node not found")

@router.post("/job/cancel")
async def cancel_job(req: JobCreateRequest, request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    job = runtime.state.active_jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found")
    job.state = "cancelled"
    runtime.store.save(runtime.state)
    logger.info(f"Job {req.job_id} cancelled by leader")
    return {"status": "cancelled", "job_id": req.job_id}

@router.post("/job/clear_finished")
async def clear_finished_jobs(request: Request):
    runtime = request.app.state.runtime
    if not hasattr(runtime, "is_leader") or not runtime.is_leader:
        raise HTTPException(status_code=403, detail="Not the leader")
    removed = []
    to_remove = [jid for jid, j in runtime.state.active_jobs.items()
                 if j.state in ("completed", "cancelled", "failed")]
    for jid in to_remove:
        del runtime.state.active_jobs[jid]
        removed.append(jid)
    runtime.store.save(runtime.state)
    logger.info(f"Cleared {len(removed)} finished jobs: {removed}")
    return {"status": "ok", "cleared_jobs": removed}
