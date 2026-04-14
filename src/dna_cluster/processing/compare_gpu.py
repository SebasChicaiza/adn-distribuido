"""
GPU-accelerated DNA chunk comparison.

Strategy (auto-detected per machine):
  1. CUDA  (cupy)   — NVIDIA GPUs on Ubuntu/Windows
  2. MPS   (torch)  — Apple Silicon on macOS
  3. CPU   (numpy)  — universal fallback, still ~100x faster than pure Python

CPU handles: file I/O (read bytes, seek)
GPU/numpy handles: the massive parallel byte-by-byte comparison
"""

import logging
from pathlib import Path
from typing import Tuple
import numpy as np

logger = logging.getLogger(__name__)

# ---- Backend detection (runs once at import time) ----

_BACKEND = "numpy"  # default fallback
_GPU_NAME = ""

try:
    import cupy as cp
    # Verify CUDA actually works
    cp.array([1, 2, 3])
    _BACKEND = "cuda"
    try:
        _GPU_NAME = cp.cuda.runtime.getDeviceProperties(0)["name"].decode()
    except Exception:
        _GPU_NAME = "NVIDIA GPU (CUDA)"
    logger.info(f"GPU backend: CUDA ({_GPU_NAME})")
except Exception:
    try:
        import torch
        if torch.backends.mps.is_available():
            _BACKEND = "mps"
            _GPU_NAME = "Apple Silicon (MPS)"
            logger.info("GPU backend: Apple MPS")
        elif torch.cuda.is_available():
            _BACKEND = "torch_cuda"
            _GPU_NAME = torch.cuda.get_device_name(0)
            logger.info(f"GPU backend: PyTorch CUDA ({_GPU_NAME})")
    except Exception:
        pass

if _BACKEND == "numpy":
    logger.info("GPU backend: none detected, using numpy vectorized CPU")


def get_backend_info() -> Tuple[str, str]:
    """Return (backend_name, gpu_name) for telemetry."""
    return _BACKEND, _GPU_NAME


# ---- Comparison kernels ----

_N_UPPER = ord("N")
_N_LOWER = ord("n")
_PLUS = ord("+")
_DOT = ord(".")


def _compare_numpy(arr_a: np.ndarray, arr_b: np.ndarray) -> np.ndarray:
    """Vectorized comparison on CPU using numpy."""
    result = np.full(len(arr_a), _DOT, dtype=np.uint8)

    is_n_upper = arr_a == _N_UPPER
    is_n_lower = arr_a == _N_LOWER
    is_equal = arr_a == arr_b

    result[is_equal] = _PLUS
    result[is_n_upper] = _N_UPPER
    result[is_n_lower] = _N_LOWER

    return result


def _compare_cuda(arr_a: np.ndarray, arr_b: np.ndarray) -> np.ndarray:
    """Vectorized comparison on NVIDIA GPU using CuPy."""
    import cupy as cp

    ga = cp.asarray(arr_a)
    gb = cp.asarray(arr_b)
    result = cp.full(len(ga), _DOT, dtype=cp.uint8)

    is_equal = ga == gb
    is_n_upper = ga == _N_UPPER
    is_n_lower = ga == _N_LOWER

    result[is_equal] = _PLUS
    result[is_n_upper] = _N_UPPER
    result[is_n_lower] = _N_LOWER

    return cp.asnumpy(result)


def _compare_mps(arr_a: np.ndarray, arr_b: np.ndarray) -> np.ndarray:
    """Vectorized comparison on Apple Silicon using PyTorch MPS."""
    import torch

    device = torch.device("mps")
    ga = torch.from_numpy(arr_a.copy()).to(device)
    gb = torch.from_numpy(arr_b.copy()).to(device)
    result = torch.full((len(ga),), _DOT, dtype=torch.uint8, device=device)

    is_equal = ga == gb
    is_n_upper = ga == _N_UPPER
    is_n_lower = ga == _N_LOWER

    result[is_equal] = _PLUS
    result[is_n_upper] = _N_UPPER
    result[is_n_lower] = _N_LOWER

    return result.cpu().numpy()


def _compare_torch_cuda(arr_a: np.ndarray, arr_b: np.ndarray) -> np.ndarray:
    """Vectorized comparison on NVIDIA GPU using PyTorch CUDA."""
    import torch

    device = torch.device("cuda")
    ga = torch.from_numpy(arr_a.copy()).to(device)
    gb = torch.from_numpy(arr_b.copy()).to(device)
    result = torch.full((len(ga),), _DOT, dtype=torch.uint8, device=device)

    is_equal = ga == gb
    is_n_upper = ga == _N_UPPER
    is_n_lower = ga == _N_LOWER

    result[is_equal] = _PLUS
    result[is_n_upper] = _N_UPPER
    result[is_n_lower] = _N_LOWER

    return result.cpu().numpy()


_COMPARE_FN = {
    "cuda": _compare_cuda,
    "mps": _compare_mps,
    "torch_cuda": _compare_torch_cuda,
    "numpy": _compare_numpy,
}


# ---- Public API (drop-in replacement for compare_cpu.compare_chunks) ----

def compare_chunks(file_a: Path, file_b: Path, start_offset: int, length: int) -> str:
    """
    Compare a byte range between two normalized genome files.
    CPU: reads bytes from disk.
    GPU/numpy: performs the vectorized comparison.
    """
    # --- CPU: file I/O ---
    with open(file_a, "rb") as fa, open(file_b, "rb") as fb:
        fa.seek(start_offset)
        fb.seek(start_offset)
        raw_a = fa.read(length)
        raw_b = fb.read(length)

    # Pad to equal length
    max_len = max(len(raw_a), len(raw_b))
    if len(raw_a) < max_len:
        raw_a += b"\x00" * (max_len - len(raw_a))
    if len(raw_b) < max_len:
        raw_b += b"\x00" * (max_len - len(raw_b))

    arr_a = np.frombuffer(raw_a, dtype=np.uint8)
    arr_b = np.frombuffer(raw_b, dtype=np.uint8)

    # --- GPU/CPU: vectorized comparison ---
    compare_fn = _COMPARE_FN[_BACKEND]
    result_arr = compare_fn(arr_a, arr_b)

    # Null-padded positions → dot
    null_mask = (arr_a == 0) | (arr_b == 0)
    result_arr[null_mask] = _DOT

    return result_arr.tobytes().decode("ascii")
