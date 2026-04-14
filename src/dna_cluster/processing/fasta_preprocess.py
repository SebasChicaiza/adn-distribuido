from pathlib import Path
import json
from .layout import LayoutMetadata
from dna_cluster.storage.paths import StoragePaths
from dna_cluster.processing.hashing import get_file_hash

class FastaPreprocessor:
    @staticmethod
    def preprocess(input_path: Path) -> tuple[Path, Path]:
        """
        Reads input .fna, outputs normalized flat sequence and metadata json.
        """
        file_hash = get_file_hash(input_path)
        normalized_path = StoragePaths.get_normalized_dir() / f"{file_hash}.norm"
        metadata_path = StoragePaths.get_normalized_dir() / f"{file_hash}.meta.json"

        if normalized_path.exists() and metadata_path.exists():
            return normalized_path, metadata_path

        layout = LayoutMetadata()
        current_offset = 0

        with open(input_path, "r", encoding="ascii", errors="ignore") as fin, \
             open(normalized_path, "w", encoding="ascii") as fnorm:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(">") or line.startswith("#"):
                    layout.add_header(line, current_offset)
                else:
                    layout.line_lengths.append(len(line))
                    fnorm.write(line)
                    current_offset += len(line)

        with open(metadata_path, "w", encoding="utf-8") as fmeta:
            fmeta.write(layout.model_dump_json(indent=2))

        return normalized_path, metadata_path
