import hashlib
from pathlib import Path

def get_file_hash(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
