import logging
import asyncio
import httpx
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
            leader_priority=settings.leader_priority,
            public_url=settings.public_url,
            state="starting"
        )
        self.loop_task = None
    
    @property
    def state(self):
        return self.node_info.state

    def start(self):
        logger.info(f"Starting NodeRuntime for {self.node_info.node_id} in {self.role_mode} mode")
        # Preprocess step
        try:
            self.node_info.state = "preprocessing"
            FastaPreprocessor.preprocess(settings.input_a_path)
            FastaPreprocessor.preprocess(settings.input_b_path)
            self.node_info.state = "ready"
            logger.info("Preprocessing complete. Node is ready.")
        except Exception as e:
            self.node_info.state = "failed"
            logger.error(f"Preprocessing failed: {e}")

    @property
    def role_mode(self):
        return self.node_info.role_mode

    async def run_loop(self):
        if self.node_info.state != "ready":
            return
        
        registered = await register_node(settings.leader_url, self.node_info)
        if not registered:
            logger.warning("Could not register with leader. Will retry later.")
        
        while True:
            try:
                await send_heartbeat(settings.leader_url, self.node_info)
                await self._poll_for_work()
            except Exception as e:
                logger.error(f"Error in node loop: {e}")
            
            await asyncio.sleep(5)

    async def _poll_for_work(self):
        if self.node_info.state == "busy":
            return

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{settings.leader_url}/api/v1/leader/chunk/request_work",
                    json={"node_id": self.node_info.node_id}
                )
                res.raise_for_status()
                data = res.json()
                
                if data.get("has_work"):
                    await self._execute_chunk(data)
        except httpx.RequestError as e:
            logger.debug(f"Could not poll work: {e}")

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
            
            result_str = compare_chunks(norm_a, norm_b, start_offset, length)
            
            # Write to local work dir
            work_dir = StoragePaths.get_work_dir() / job_id
            work_dir.mkdir(parents=True, exist_ok=True)
            res_path = work_dir / f"{chunk_id}.res"
            with open(res_path, "w", encoding="utf-8") as f:
                f.write(result_str)
                
            logger.info(f"Finished processing {chunk_id}, uploading result...")
            
            # Upload
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{settings.leader_url}/api/v1/leader/chunk/result",
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
            logger.error(f"Failed to process chunk {chunk_id}: {e}")
        finally:
            self.node_info.state = "ready"
