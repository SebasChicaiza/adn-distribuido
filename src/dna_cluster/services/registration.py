import httpx
import logging
from dna_cluster.models.node import NodeInfo

logger = logging.getLogger(__name__)

async def register_node(leader_url: str, node_info: NodeInfo):
    logger.info(f"Registering node {node_info.node_id} to {leader_url}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{leader_url}/api/v1/leader/register",
                json={"node_info": node_info.model_dump()}
            )
            response.raise_for_status()
            logger.info("Successfully registered with leader.")
            return True
    except Exception as e:
        logger.error(f"Failed to register with leader: {e}")
        return False
