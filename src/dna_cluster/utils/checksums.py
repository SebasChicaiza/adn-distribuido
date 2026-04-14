import hashlib

def calculate_checksum(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
