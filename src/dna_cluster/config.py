import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    node_id: str = "node_local"
    role_mode: str = "worker" # Can be 'worker', 'worker_standby', 'standby'
    leader_priority: int = 10
    public_url: str = "http://localhost:8000"
    cluster_nodes: str = "" # Format: node_id,public_url,priority;node_id,public_url,priority
    data_dir: Path = Path("./data")
    input_a_path: Path = Path("./data/input/a.fna")
    input_b_path: Path = Path("./data/input/b.fna")
    log_level: str = "INFO"
    chunk_size_bytes: int = 100 * 1024 * 1024 # 100MB chunk for local processing
    api_port: int = 8000
    api_host: str = "0.0.0.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def parsed_cluster_nodes_info(self) -> List[dict]:
        if not self.cluster_nodes:
            return []
        nodes = []
        for n in self.cluster_nodes.split(";"):
            parts = n.strip().split(",")
            if len(parts) == 3:
                nodes.append({
                    "node_id": parts[0].strip(),
                    "public_url": parts[1].strip(),
                    "priority": int(parts[2].strip())
                })
            elif len(parts) == 1 and parts[0]:
                # Fallback for old config
                nodes.append({
                    "node_id": parts[0].strip(),
                    "public_url": "http://localhost:8001",
                    "priority": 0
                })
        return nodes

settings = Settings()
