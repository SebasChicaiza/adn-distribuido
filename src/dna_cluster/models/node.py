from pydantic import BaseModel
from typing import Optional

class NodeInfo(BaseModel):
    node_id: str
    role_mode: str
    leader_priority: int
    public_url: str
    state: str = "offline" # offline, starting, ready, busy
    term: int = 0
    
    # Telemetry
    available_ram_bytes: int = 0
    total_ram_bytes: int = 0
    cpu_count: int = 0
    cpu_load_percent: float = 0.0
    disk_free_bytes: int = 0
    gpu_available: bool = False
    gpu_name: str = ""
    active_tasks: int = 0
    cpu_benchmark_mb_s: float = 0.0
    last_seen_at: float = 0.0
    is_disabled: bool = False
