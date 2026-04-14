from pathlib import Path

def compare_chunks(file_a: Path, file_b: Path, start_offset: int, length: int) -> str:
    """
    Compare a specific byte range between two normalized files.
    Uses binary mode to ensure seek() works with exact byte offsets.
    """
    with open(file_a, "rb") as fa, open(file_b, "rb") as fb:
        fa.seek(start_offset)
        fb.seek(start_offset)
        
        chunk_a = fa.read(length)
        chunk_b = fb.read(length)
        
        result = []
        max_len = max(len(chunk_a), len(chunk_b))
        for i in range(max_len):
            byte_a = chunk_a[i:i+1] if i < len(chunk_a) else b""
            byte_b = chunk_b[i:i+1] if i < len(chunk_b) else b""
            
            if not byte_a and byte_b:
                result.append(".")
            elif byte_a and not byte_b:
                result.append(".")
            elif byte_a in (b"N", b"n"):
                result.append(byte_a.decode("ascii", errors="replace"))
            elif byte_a == byte_b:
                result.append("+")
            else:
                result.append(".")
        return "".join(result)
