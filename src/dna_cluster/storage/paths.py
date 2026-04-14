from pathlib import Path
from dna_cluster.config import settings

class StoragePaths:
    @staticmethod
    def _ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_data_dir(cls) -> Path:
        return cls._ensure_dir(settings.data_dir)

    @classmethod
    def get_normalized_dir(cls) -> Path:
        return cls._ensure_dir(cls.get_data_dir() / "normalized")
    
    @classmethod
    def get_work_dir(cls) -> Path:
        return cls._ensure_dir(cls.get_data_dir() / "work")

    @classmethod
    def get_output_dir(cls) -> Path:
        return cls._ensure_dir(cls.get_data_dir() / "output")

    @classmethod
    def get_state_dir(cls) -> Path:
        return cls._ensure_dir(cls.get_data_dir() / "state")
