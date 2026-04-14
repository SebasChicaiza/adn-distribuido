import logging
import time
from pathlib import Path
from typing import Optional, Tuple
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
        self.state = self.store.load() or ClusterState(term=1, leader_id=settings.node_id)
        for n in settings.parsed_cluster_nodes:
            if n not in self.state.known_nodes:
                self.state.known_nodes.append(n)
        self.store.save(self.state)

    def start(self):
        logger.info(f"Starting LeaderRuntime, current term {self.state.term}")

    def register_node(self, node_info):
        self.state.nodes[node_info.node_id] = node_info
        if node_info.node_id not in self.state.known_nodes:
            self.state.known_nodes.append(node_info.node_id)
        self.store.save(self.state)
        logger.info(f"Registered node {node_info.node_id}")

    def update_node_heartbeat(self, node_info):
        self.state.nodes[node_info.node_id] = node_info

    def create_job(self, job_id: str):
        logger.info(f"Creating job {job_id}")
        if job_id in self.state.active_jobs:
            raise ValueError(f"Job {job_id} already exists")
        
        # Preprocess if not done, then chunk
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
            
        # Save durable output part
        parts_dir = StoragePaths.get_output_dir() / "parts" / job_id
        parts_dir.mkdir(parents=True, exist_ok=True)
        chunk_file_path = parts_dir / f"{chunk_id}.res"
        with open(chunk_file_path, "w", encoding="utf-8") as f:
            f.write(result_data)
        
        # Mark as committed
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
