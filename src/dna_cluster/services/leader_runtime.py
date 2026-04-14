import logging
import time
import asyncio
import httpx
import psutil
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict
from dna_cluster.models.cluster import ClusterState
from dna_cluster.models.node import NodeInfo
from dna_cluster.models.job import JobInfo
from dna_cluster.models.chunk import ChunkState, ChunkInfo
from dna_cluster.storage.state_store import StateStore
from dna_cluster.storage.paths import StoragePaths
from dna_cluster.config import settings
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor
from dna_cluster.processing.hashing import get_file_hash
from dna_cluster.processing.chunking import chunk_file
from dna_cluster.processing.assemble_output import assemble_final_output
from dna_cluster.processing.compare_cpu import compare_chunks
from dna_cluster.services.registration import register_node
from dna_cluster.services.heartbeat import send_heartbeat

logger = logging.getLogger(__name__)

class LeaderRuntime:
    def __init__(self):
        self.store = StateStore()
        self.state = self.store.load() or ClusterState()
        self.startup_at = time.time()
        
        my_info = self._get_my_node_info()
        self.node_info = NodeInfo(
            node_id=settings.node_id,
            role_mode=settings.role_mode,
            leader_priority=my_info["priority"],
            public_url=settings.public_url,
            state="ready"
        )
        
        self.is_leader = False
        self.is_processing = False
        
        if self.state.term == 0:
            self.state.term = 1
            if settings.parsed_cluster_nodes_info:
                highest_priority_node = max(settings.parsed_cluster_nodes_info, key=lambda x: x["priority"])
                logger.info(f"Initial startup. Highest priority node in config: {highest_priority_node['node_id']} (Prio: {highest_priority_node['priority']}). My ID: {settings.node_id}")
                if highest_priority_node["node_id"] == settings.node_id:
                    self.is_leader = True
                    self.state.leader_id = settings.node_id
                    self.state.leader_last_heartbeat_at = time.time()
            else:
                logger.warning("Initial startup with no cluster nodes configured. Not becoming leader yet.")
            self.store.save(self.state)
        elif self.state.leader_id == settings.node_id:
            self.is_leader = True
            self.state.leader_last_heartbeat_at = time.time()
        else:
            logger.info(f"Loaded existing state with Leader: {self.state.leader_id}, Term: {self.state.term}. My ID: {settings.node_id}")

    def _get_my_node_info(self):
        for n in settings.parsed_cluster_nodes_info:
            if n["node_id"] == settings.node_id:
                return n
        return {"node_id": settings.node_id, "priority": 0, "public_url": settings.public_url}

    def start(self):
        logger.info(f"Starting LeaderRuntime. Is Leader: {self.is_leader}, Term: {self.state.term}")

    async def run_loop(self):
        while True:
            try:
                self._refresh_telemetry()
                if self.is_leader:
                    self._update_my_node_in_state()
                    self._check_stuck_chunks()
                    await self._replicate_state()
                    if "worker" in settings.role_mode:
                        await self._leader_worker_step()
                else:
                    self._check_lease()
                    if "worker" in settings.role_mode:
                        await self._standby_worker_step()
            except Exception as e:
                logger.error(f"Error in leader run_loop: {e}")
            await asyncio.sleep(5)

    def _refresh_telemetry(self):
        try:
            mem = psutil.virtual_memory()
            self.node_info.available_ram_bytes = mem.available
            self.node_info.total_ram_bytes = mem.total
            self.node_info.cpu_count = psutil.cpu_count(logical=True) or 1
            self.node_info.cpu_load_percent = psutil.cpu_percent()
            disk = shutil.disk_usage(settings.data_dir)
            self.node_info.disk_free_bytes = disk.free
            self.node_info.term = self.state.term
        except Exception:
            pass

    def _update_my_node_in_state(self):
        self.node_info.last_seen_at = time.time()
        self.node_info.state = "ready" if not self.is_processing else "busy"
        self.state.nodes[settings.node_id] = self.node_info
        self.state.leader_last_heartbeat_at = time.time()

    async def _leader_worker_step(self):
        if self.is_processing:
            return
        work = self.request_work(settings.node_id)
        if work:
            job_id, chunk = work
            self.is_processing = True
            try:
                # Direct execution as leader
                await self._execute_chunk_local(job_id, chunk)
            finally:
                self.is_processing = False

    async def _standby_worker_step(self):
        if self.is_processing or not self.state.leader_id:
            return
        
        # Get leader URL from config
        leader_info = next((n for n in settings.parsed_cluster_nodes_info if n["node_id"] == self.state.leader_id), None)
        if not leader_info:
            return
        
        leader_url = leader_info["public_url"]
        
        try:
            # Register and Heartbeat to show up in dashboard
            await register_node(leader_url, self.node_info)
            await send_heartbeat(leader_url, self.node_info)
            
            # Poll for work
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{leader_url}/api/v1/leader/chunk/request_work",
                    json={"node_id": settings.node_id}
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("has_work"):
                        self.is_processing = True
                        try:
                            await self._execute_chunk_remote(leader_url, data)
                        finally:
                            self.is_processing = False
        except Exception as e:
            logger.debug(f"Standby worker poll failed: {e}")

    async def _execute_chunk_local(self, job_id: str, chunk: ChunkInfo):
        logger.info(f"Leader processing own chunk {chunk.chunk_id} for job {job_id}")
        try:
            norm_a, _ = FastaPreprocessor.preprocess(settings.input_a_path)
            norm_b, _ = FastaPreprocessor.preprocess(settings.input_b_path)
            
            result_str = compare_chunks(norm_a, norm_b, chunk.start_offset, chunk.length)
            self.commit_chunk_result(chunk.chunk_id, job_id, result_str)
        except Exception as e:
            logger.error(f"Leader failed to process local chunk: {e}")

    async def _execute_chunk_remote(self, leader_url: str, data: dict):
        chunk_id = data["chunk_id"]
        job_id = data["job_id"]
        logger.info(f"Standby processing remote chunk {chunk_id} for job {job_id}")
        
        try:
            norm_a, _ = FastaPreprocessor.preprocess(settings.input_a_path)
            norm_b, _ = FastaPreprocessor.preprocess(settings.input_b_path)
            
            result_str = compare_chunks(norm_a, norm_b, data["start_offset"], data["length"])
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{leader_url}/api/v1/leader/chunk/result",
                    json={
                        "node_id": settings.node_id,
                        "chunk_id": chunk_id,
                        "job_id": job_id,
                        "result_data": result_str
                    }
                )
            logger.info(f"Successfully uploaded result for {chunk_id}")
        except Exception as e:
            logger.error(f"Standby failed to process/upload chunk: {e}")

    def _check_lease(self):
        now = time.time()
        
        if self.state.leader_id and self.state.leader_id != settings.node_id:
            leader_node = self.state.nodes.get(self.state.leader_id)
            my_info = self._get_my_node_info()
            
            leader_prio = leader_node.leader_priority if leader_node else 0
            if not leader_prio:
                 leader_info = next((n for n in settings.parsed_cluster_nodes_info if n["node_id"] == self.state.leader_id), None)
                 if leader_info:
                     leader_prio = leader_info["priority"]

            if my_info["priority"] > leader_prio:
                time_since_heartbeat = now - self.state.leader_last_heartbeat_at
                if time_since_heartbeat > 15.0:
                    logger.info(f"Preempting lower priority leader {self.state.leader_id} (Prio: {leader_prio} < {my_info['priority']})")
                    self._attempt_promotion()
                    return

        if not self.state.leader_id:
            if now - self.startup_at < 15.0:
                return
            self._attempt_promotion()
            return

        time_since_heartbeat = now - self.state.leader_last_heartbeat_at
        if time_since_heartbeat > 45.0:
            logger.warning(f"Leader lease expired! Last heartbeat {time_since_heartbeat:.1f}s ago.")
            self._attempt_promotion()

    def _attempt_promotion(self):
        my_info = self._get_my_node_info()
        my_priority = my_info["priority"]
        
        now = time.time()
        for n_id, n in self.state.nodes.items():
            if n_id != settings.node_id and not n.is_disabled and (now - n.last_seen_at < 30.0):
                if n.leader_priority > my_priority:
                    logger.debug(f"Skipping promotion: node {n_id} has higher priority ({n.leader_priority} > {my_priority}) and is alive.")
                    return

        logger.info(f"Node {settings.node_id} attempting promotion to leader.")
        self.state.term += 1
        self.state.leader_id = settings.node_id
        self.is_leader = True
        self.state.leader_last_heartbeat_at = now
        self.store.save(self.state)
        logger.info(f"Promoted to LEADER! New term: {self.state.term}")

    async def _replicate_state(self):
        state_json = self.state.model_dump_json()
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            for node_info in settings.parsed_cluster_nodes_info:
                if node_info["node_id"] == settings.node_id:
                    continue
                try:
                    url = f"{node_info['public_url']}/api/v1/leader/state/sync"
                    await client.post(url, json={"state_json": state_json})
                except Exception as e:
                    logger.debug(f"Failed to replicate state to {node_info['node_id']}: {e}")

    def receive_state_sync(self, state_json: str):
        try:
            new_state = ClusterState.model_validate_json(state_json)
        except Exception as e:
            logger.error(f"Failed to validate received state: {e}")
            return

        my_info = self._get_my_node_info()
        my_priority = my_info["priority"]
        
        if new_state.term > self.state.term:
            logger.info(f"Yielding to higher term: {new_state.term} > {self.state.term} (Leader: {new_state.leader_id})")
            self.is_leader = False
            self.state = new_state
            self.state.leader_last_heartbeat_at = time.time()
            self.store.save(self.state)
            return

        if new_state.term < self.state.term:
            if self.is_leader:
                 logger.warning(f"Ignoring state sync with older term ({new_state.term} < {self.state.term}) from {new_state.leader_id}. I am the current leader.")
            return

        leader_prio = 0
        leader_info = next((n for n in settings.parsed_cluster_nodes_info if n["node_id"] == new_state.leader_id), None)
        if leader_info:
            leader_prio = leader_info["priority"]

        if leader_prio > my_priority:
            if self.is_leader:
                logger.info(f"Yielding leadership to higher priority node {new_state.leader_id} in term {new_state.term}")
                self.is_leader = False
            self.state = new_state
            self.state.leader_last_heartbeat_at = time.time()
            self.store.save(self.state)
        elif leader_prio < my_priority:
            if self.is_leader:
                logger.debug(f"Received sync from lower priority node {new_state.leader_id} in term {self.state.term}. Ignoring.")
        else:
            if new_state.leader_id > settings.node_id:
                if self.is_leader:
                    logger.info(f"Yielding leadership to node {new_state.leader_id} (ID tie-break) in term {new_state.term}")
                    self.is_leader = False
                self.state = new_state
                self.state.leader_last_heartbeat_at = time.time()
                self.store.save(self.state)

    def _check_stuck_chunks(self):
        now = time.time()
        for job_id, job in self.state.active_jobs.items():
            if job.state != "running":
                continue
            for chunk_id, chunk in job.chunks.items():
                if chunk.state in [ChunkState.ASSIGNED, ChunkState.IN_PROGRESS]:
                    assigned_node = self.state.nodes.get(chunk.assigned_node)
                    if not assigned_node or (now - assigned_node.last_seen_at > 30.0) or (now - chunk.assigned_at > 60.0):
                        logger.warning(f"Chunk {chunk_id} stuck on node {chunk.assigned_node}. Requeuing.")
                        chunk.state = ChunkState.RETRY
                        chunk.assigned_node = None
                        self.store.save(self.state)

    def register_node(self, node_info):
        node_info.last_seen_at = time.time()
        existing = self.state.nodes.get(node_info.node_id)
        if existing:
            node_info.is_disabled = existing.is_disabled
            node_info.leader_priority = existing.leader_priority
        self.state.nodes[node_info.node_id] = node_info
        self.store.save(self.state)
        logger.info(f"Registered node {node_info.node_id}")

    def update_node_heartbeat(self, node_info):
        node_info.last_seen_at = time.time()
        existing = self.state.nodes.get(node_info.node_id)
        if existing:
            node_info.is_disabled = existing.is_disabled
            node_info.leader_priority = existing.leader_priority
        self.state.nodes[node_info.node_id] = node_info

    def create_job(self, job_id: str):
        logger.info(f"Creating job {job_id}")
        if job_id in self.state.active_jobs:
            raise ValueError(f"Job {job_id} already exists")
        
        norm_a, _ = FastaPreprocessor.preprocess(settings.input_a_path)
        
        chunk_size = settings.chunk_size_bytes
        for n in self.state.nodes.values():
            if not n.is_disabled and n.available_ram_bytes > 0 and n.available_ram_bytes < 2 * 1024**3:
                chunk_size = 20 * 1024 * 1024
                logger.info(f"Found low RAM node {n.node_id}, adjusting chunk size to {chunk_size} bytes")
                break

        chunks = chunk_file(norm_a, job_id, chunk_size)
        
        job_info = JobInfo(
            job_id=job_id,
            input_a_hash="stub_hash_a",
            input_b_hash="stub_hash_b",
            total_chunks=len(chunks),
            state="running"
        )
        for chunk in chunks:
            job_info.chunks[chunk.chunk_id] = chunk

        self.state.active_jobs[job_id] = job_info
        self.store.save(self.state)
        logger.info(f"Job {job_id} created with {len(chunks)} chunks.")

    def _calculate_node_score(self, node: NodeInfo) -> int:
        if node.is_disabled: return -1000
        score = 0
        if node.available_ram_bytes > 8 * 1024**3: score += 50
        elif node.available_ram_bytes > 4 * 1024**3: score += 20
        score += node.cpu_count * 5
        score -= node.active_tasks * 20
        return score

    def request_work(self, node_id: str) -> Optional[Tuple[str, ChunkInfo]]:
        node = self.state.nodes.get(node_id)
        if not node or node.is_disabled:
            return None

        if self.state.scheduler_mode == "pin_single_node":
            if node_id != self.state.pinned_node_id:
                return None
                
        elif self.state.scheduler_mode == "weighted":
            my_score = self._calculate_node_score(node)
            now = time.time()
            best_score = max([self._calculate_node_score(n) for n in self.state.nodes.values() if (now - n.last_seen_at < 30.0)], default=my_score)
            if my_score < best_score - 30:
                return None

        for job_id, job in self.state.active_jobs.items():
            if job.state != "running":
                continue
            for chunk_id, chunk in job.chunks.items():
                if chunk.state == ChunkState.PENDING or chunk.state == ChunkState.RETRY:
                    chunk.state = ChunkState.ASSIGNED
                    chunk.assigned_node = node_id
                    chunk.assigned_at = time.time()
                    self.store.save(self.state)
                    return job_id, chunk
        return None

    def commit_chunk_result(self, chunk_id: str, job_id: str, result_data: str):
        job = self.state.active_jobs.get(job_id)
        if not job:
            return
        chunk = job.chunks.get(chunk_id)
        if not chunk:
            return
            
        parts_dir = StoragePaths.get_output_dir() / "parts" / job_id
        parts_dir.mkdir(parents=True, exist_ok=True)
        chunk_file_path = parts_dir / f"{chunk_id}.res"
        with open(chunk_file_path, "w", encoding="utf-8") as f:
            f.write(result_data)
        
        chunk.state = ChunkState.COMMITTED
        self.store.save(self.state)
        logger.info(f"Committed chunk {chunk_id} for job {job_id}")

        self._check_job_completion(job_id)

    def _check_job_completion(self, job_id: str):
        job = self.state.active_jobs.get(job_id)
        if not job:
            return
        
        all_committed = all(c.state == ChunkState.COMMITTED for c in job.chunks.values())
        if all_committed:
            logger.info(f"Job {job_id} is complete! Assembling final output...")
            parts_dir = StoragePaths.get_output_dir() / "parts" / job_id
            _, meta_path = FastaPreprocessor.preprocess(settings.input_a_path)
            output_path = StoragePaths.get_output_dir() / f"result_{job_id}.fna"
            
            try:
                assemble_final_output(job_id, parts_dir, meta_path, output_path)
                job.state = "completed"
                self.store.save(self.state)
                logger.info(f"Final output assembled successfully at {output_path}")
            except Exception as e:
                logger.error(f"Failed to assemble final output for job {job_id}: {e}")
                job.state = "failed"
                self.store.save(self.state)
