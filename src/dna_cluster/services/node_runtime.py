import logging
import asyncio
import httpx
import psutil
import shutil
import time
from typing import Optional, Tuple
from dna_cluster.config import settings
from dna_cluster.models.node import NodeInfo
from dna_cluster.processing.fasta_preprocess import FastaPreprocessor
from dna_cluster.processing.compare_cpu import compare_chunks
from dna_cluster.services.registration import register_node
from dna_cluster.services.heartbeat import send_heartbeat
from dna_cluster.storage.paths import StoragePaths

logger = logging.getLogger(__name__)

class NodeRuntime:
    def __init__(self):
        self.node_info = NodeInfo(
            node_id=settings.node_id,
            role_mode=settings.role_mode,
            leader_priority=settings.my_priority,
            public_url=settings.public_url,
            state="starting"
        )
        self.current_leader_url = None
        self.current_term = 0
    
    @property
    def state(self):
        return self.node_info.state

    @property
    def role_mode(self):
        return self.node_info.role_mode

    def start(self):
        logger.info(f"Starting NodeRuntime for {self.node_info.node_id} in {self.role_mode} mode")
        try:
            self.node_info.state = "preprocessing"
            FastaPreprocessor.preprocess(settings.input_a_path)
            FastaPreprocessor.preprocess(settings.input_b_path)
            self.node_info.state = "ready"
            logger.info("Preprocessing complete. Node is ready.")
        except Exception as e:
            self.node_info.state = "failed"
            logger.error(f"Preprocessing failed: {e}")

    def _update_telemetry(self):
        try:
            mem = psutil.virtual_memory()
            self.node_info.available_ram_bytes = mem.available
            self.node_info.total_ram_bytes = mem.total
            self.node_info.cpu_count = psutil.cpu_count(logical=True) or 1
            self.node_info.cpu_load_percent = psutil.cpu_percent()
            disk = shutil.disk_usage(settings.data_dir)
            self.node_info.disk_free_bytes = disk.free
        except Exception:
            pass

    async def _find_leader(self) -> bool:
        best_leader_url = None
        highest_term = -1
        best_priority = -1

        async with httpx.AsyncClient(timeout=5.0) as client:
            for node_info in settings.parsed_cluster_nodes_info:
                try:
                    res = await client.get(f"{node_info['public_url']}/api/v1/status")
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("is_leader"):
                            term = data.get("term", 0)
                            prio = node_info["priority"]
                            if term > highest_term:
                                highest_term = term
                                best_priority = prio
                                best_leader_url = node_info["public_url"]
                            elif term == highest_term and prio > best_priority:
                                best_priority = prio
                                best_leader_url = node_info["public_url"]
                except Exception:
                    pass

        if best_leader_url:
            if best_leader_url != self.current_leader_url:
                logger.info(f"Found new active leader at {best_leader_url} (term {highest_term})")
                self.current_leader_url = best_leader_url
                self.current_term = highest_term
            return True
        return False

    async def run_loop(self):
        # Wait until ready
        while self.node_info.state == "starting" or self.node_info.state == "preprocessing":
            await asyncio.sleep(1)
            
        if self.node_info.state != "ready":
            logger.error(f"Node loop aborted because state is {self.node_info.state}")
            return
        
        while True:
            self._update_telemetry()
            try:
                if not self.current_leader_url:
                    found = await self._find_leader()
                    if found:
                        registered = await register_node(self.current_leader_url, self.node_info)
                        if not registered:
                            self.current_leader_url = None # Retry finding leader if registration fails
                
                if self.current_leader_url:
                    try:
                        await send_heartbeat(self.current_leader_url, self.node_info)
                        await self._poll_for_work()
                    except Exception as e:
                        logger.warning(f"Connection lost to leader {self.current_leader_url}: {e}")
                        self.current_leader_url = None # Trigger leader rediscovery
            except Exception as e:
                logger.error(f"Error in node loop: {e}")
            
            await asyncio.sleep(5)

    async def _poll_for_work(self):
        if self.node_info.state == "busy" or not self.current_leader_url:
            return

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{self.current_leader_url}/api/v1/leader/chunk/request_work",
                    json={"node_id": self.node_info.node_id}
                )
                res.raise_for_status()
                data = res.json()
                
                if data.get("has_work"):
                    await self._execute_chunk(data)
        except httpx.RequestError as e:
            logger.debug(f"Could not poll work: {e}")
            raise e # Pass up to reset leader URL

    async def _execute_chunk(self, data: dict):
        chunk_id = data["chunk_id"]
        job_id = data["job_id"]
        start_offset = data["start_offset"]
        length = data["length"]
        
        logger.info(f"Assigned chunk {chunk_id} for job {job_id}")
        self.node_info.state = "busy"
        
        try:
            norm_a, _ = FastaPreprocessor.preprocess(settings.input_a_path)
            norm_b, _ = FastaPreprocessor.preprocess(settings.input_b_path)
            
            from dna_cluster.processing.compare_cpu import compare_chunks
            result_str = compare_chunks(norm_a, norm_b, start_offset, length)
            
            work_dir = StoragePaths.get_work_dir() / job_id
            work_dir.mkdir(parents=True, exist_ok=True)
            res_path = work_dir / f"{chunk_id}.res"
            with open(res_path, "w", encoding="utf-8") as f:
                f.write(result_str)
                
            logger.info(f"Finished processing {chunk_id}, uploading result to {self.current_leader_url}...")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.current_leader_url}/api/v1/leader/chunk/result",
                    json={
                        "node_id": self.node_info.node_id,
                        "chunk_id": chunk_id,
                        "job_id": job_id,
                        "result_data": result_str
                    }
                )
                res.raise_for_status()
            logger.info(f"Successfully uploaded {chunk_id}")
            
        except Exception as e:
            logger.error(f"Failed to process/upload chunk {chunk_id}: {e}")
            raise e # If it was a network error during upload, this will drop current_leader_url, which is good.
        finally:
            self.node_info.state = "ready"
