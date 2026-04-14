import json
from pathlib import Path
from typing import Optional
from dna_cluster.models.cluster import ClusterState
from dna_cluster.storage.paths import StoragePaths

class StateStore:
    def __init__(self):
        self.state_file = StoragePaths.get_state_dir() / "cluster_state.json"

    def save(self, state: ClusterState):
        with open(self.state_file, "w") as f:
            f.write(state.model_dump_json(indent=2))

    def load(self) -> Optional[ClusterState]:
        if not self.state_file.exists():
            return None
        with open(self.state_file, "r") as f:
            try:
                data = json.load(f)
                return ClusterState(**data)
            except Exception:
                return None
