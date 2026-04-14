from pathlib import Path

def compare_chunks(file_a: Path, file_b: Path, start_offset: int, length: int) -> str:
    """
    Compare a specific byte range between two normalized files.
    """
    with open(file_a, "r", encoding="utf-8") as fa, open(file_b, "r", encoding="utf-8") as fb:
        fa.seek(start_offset)
        fb.seek(start_offset)
        
        chunk_a = fa.read(length)
        chunk_b = fb.read(length)
        
        result = []
        max_len = max(len(chunk_a), len(chunk_b))
        for i in range(max_len):
            char_a = chunk_a[i] if i < len(chunk_a) else ""
            char_b = chunk_b[i] if i < len(chunk_b) else ""
            
            if not char_a and char_b:
                result.append(".")
            elif char_a and not char_b:
                result.append(".")
            elif char_a in ("N", "n"):
                result.append(char_a)
            elif char_a == char_b:
                result.append("+")
            else:
                result.append(".")
        return "".join(result)
