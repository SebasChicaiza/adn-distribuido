from typing import List, Dict, Any
from pydantic import BaseModel

class LayoutMetadata(BaseModel):
    headers: List[Dict[str, Any]] = [] # { "offset": int, "text": str }
    line_lengths: List[int] = [] # Original lengths of sequence lines to reconstruct

    def add_header(self, text: str, normalized_offset: int):
        self.headers.append({"offset": normalized_offset, "text": text})
