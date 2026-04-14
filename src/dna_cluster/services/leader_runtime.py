import logging
import time
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Tuple, Dict
from dna_cluster.models.cluster import ClusterState
from dna_cluster.models.job import JobInfo
from dna_cluster.models.chunk import ChunkState, ChunkInfo
from dna_cluster.storage.state_store import StateStore
from dna_cluster.storage.paths import StoragePaths
from dna_cluster.config import settings
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor
from dna_cluster.processing.chunking import chunk_file
from dna_cluster.processing.assemble_output import assemble_final_output

logger = logging.getLogger(__name__)

class LeaderRuntime:
    def __init__(self):
        self.store = StateStore()
        self.state = self.store.load() or ClusterState()
        
        # Determine if we are the initial leader by priority if no state exists
        me = self._get_my_node_info()
        self.is_leader = False
        
        if self.state.term == 0:
            self.state.term = 1
            # If I have the highest priority initially, I start as leader
            highest_priority_node = max(settings.parsed_cluster_nodes_info, key=lambda x: x["priority"])
            if highest_priority_node["node_id"] == settings.node_id:
                self.is_leader = True
                self.state.leader_id = settings.node_id
            self.store.save(self.state)
        elif self.state.leader_id == settings.node_id:
            self.is_leader = True

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
                if self.is_leader:
                    await self._replicate_state()
                else:
                    self._check_lease()
            except Exception as e:
                logger.error(f"Error in leader run_loop: {e}")
            await asyncio.sleep(5)

    def _check_lease(self):
        if not self.state.leader_id:
            return
            
        time_since_heartbeat = time.time() - self.state.leader_last_heartbeat_at
        if time_since_heartbeat > 15.0:
            logger.warning(f"Leader lease expired! Last heartbeat {time_since_heartbeat:.1f}s ago.")
            self._attempt_promotion()

    def _attempt_promotion(self):
        my_info = self._get_my_node_info()
        # Find healthy standbys. In a real system, we'd ping them. Here we assume config priority dictates order.
        # Check if any higher priority node is alive. For simplicity, we just promote if we are highest priority 
        # among those that seem active, or just strictly based on config priority assuming failed nodes won't fight.
        # Since this is a practical student project failover:
        higher_priority_nodes = [n for n in settings.parsed_cluster_nodes_info if n["priority"] > my_info["priority"]]
        
        # If we have the highest priority, or if we assume higher ones are dead (simplified logic):
        # We will aggressively promote if we haven't heard from the leader.
        # A more robust check would ping higher_priority_nodes first.
        logger.info(f"Node {settings.node_id} attempting promotion to leader.")
        self.state.term += 1
        self.state.leader_id = settings.node_id
        self.is_leader = True
        self.state.leader_last_heartbeat_at = time.time()
        self.store.save(self.state)
        logger.info(f"Promoted to LEADER! New term: {self.state.term}")

    async def _replicate_state(self):
        # Push state to all known standbys
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
        if self.is_leader:
            logger.warning("Received state sync but I am the leader. Ignoring.")
            return
            
        new_state = ClusterState.model_validate_json(state_json)
        if new_state.term >= self.state.term:
            self.state = new_state
            self.state.leader_last_heartbeat_at = time.time()
            self.store.save(self.state)
            logger.debug(f"State synced from leader {self.state.leader_id}, term {self.state.term}")
        else:
            logger.warning("Received state sync with older term.")

    def register_node(self, node_info):
        self.state.nodes[node_info.node_id] = node_info
        self.store.save(self.state)
        logger.info(f"Registered node {node_info.node_id}")

    def update_node_heartbeat(self, node_info):
        self.state.nodes[node_info.node_id] = node_info

    def create_job(self, job_id: str):
        logger.info(f"Creating job {job_id}")
        if job_id in self.state.active_jobs:
            raise ValueError(f"Job {job_id} already exists")
        
        norm_a, meta_a = FastaPreprocessor.preprocess(settings.input_a_path)
        chunks = chunk_file(norm_a, job_id)
        
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

    def request_work(self, node_id: str) -> Optional[Tuple[str, ChunkInfo]]:
        for job_id, job in self.state.active_jobs.items():
            if job.state != "running":
                continue
            for chunk_id, chunk in job.chunks.items():
                if chunk.state == ChunkState.PENDING or chunk.state == ChunkState.RETRY:
                    chunk.state = ChunkState.ASSIGNED
                    chunk.assigned_node = node_id
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
