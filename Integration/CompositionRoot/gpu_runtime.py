"""Local accelerator diagnostics; no Engine ownership is introduced."""
from functools import lru_cache


@lru_cache(maxsize=1)
def accelerator_diagnostics():
    """Discover immutable process accelerator properties once.

    Re-entering the CUDA runtime from status-request threads while YOLO is
    executing can block inference. Hardware identity does not change during a
    TaskGraph process, so all runtime projections reuse the initial snapshot.
    """
    result = {"torch_version": None, "cuda_available": False, "cuda_version": None, "gpu_name": None, "device": "CPU", "cuda_error": None}
    try:
        import torch
        result.update(torch_version=torch.__version__, cuda_version=torch.version.cuda, cuda_available=bool(torch.cuda.is_available()))
        if result["cuda_available"]:
            try:
                torch.cuda.init()
                result.update(gpu_name=torch.cuda.get_device_name(0), device="CUDA")
            except Exception as exc:
                result.update(cuda_available=False, device="CUDA Initialization Failed", cuda_error=f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        result["cuda_error"] = f"{type(exc).__name__}: {exc}"
    return result
