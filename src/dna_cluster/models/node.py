from pydantic import BaseModel
from typing import Optional

class NodeInfo(BaseModel):
    node_id: str
    role_mode: str
    leader_priority: int
    public_url: str
    state: str = "offline" # offline, starting, ready, busy
    term: int = 0
