import httpx
import logging
from dna_cluster.models.node import NodeInfo

logger = logging.getLogger(__name__)

async def send_heartbeat(leader_url: str, node_info: NodeInfo):
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                f"{leader_url}/api/v1/leader/heartbeat",
                json={"node_info": node_info.model_dump()}
            )
            response.raise_for_status()
    except Exception as e:
        logger.debug(f"Heartbeat failed: {e}")
