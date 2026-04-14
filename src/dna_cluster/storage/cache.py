from pathlib import Path

class CacheStore:
    # A simple phase 1 cache mechanism based on file existence
    @staticmethod
    def is_cached(filepath: Path) -> bool:
        return filepath.exists() and filepath.stat().st_size > 0
