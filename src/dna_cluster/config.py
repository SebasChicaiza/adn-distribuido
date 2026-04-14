import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    node_id: str = "node_local"
    role_mode: str = "worker" # Can be 'worker', 'worker_standby', 'standby'
    leader_priority: int = 10
    public_url: str = "http://localhost:8000"
    leader_url: str = "http://localhost:8001"
    cluster_nodes: str = "" # Comma separated list of known node IDs
    data_dir: Path = Path("./data")
    input_a_path: Path = Path("./data/input/a.fna")
    input_b_path: Path = Path("./data/input/b.fna")
    log_level: str = "INFO"
    chunk_size_bytes: int = 10 * 1024 * 1024 # 10MB chunk for local processing
    api_port: int = 8000
    api_host: str = "0.0.0.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def parsed_cluster_nodes(self) -> List[str]:
        if not self.cluster_nodes:
            return []
        return [n.strip() for n in self.cluster_nodes.split(",") if n.strip()]

settings = Settings()
