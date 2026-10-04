"""Speech-to-text with faster-whisper, run on the GPU when one is available."""
from __future__ import annotations

import ctypes
import gc
import glob
import os
import site
import wave
from pathlib import Path
from typing import Callable

from .config import WHISPER_DEVICE, WHISPER_MODEL
from .models import Segment


def _preload_cuda_libs() -> None:
    """Load cuBLAS/cuDNN from the nvidia-* pip wheels so no system CUDA install is needed."""
    for sp in site.getsitepackages():
        for pattern in ("nvidia/cublas/lib/libcublas*.so.*", "nvidia/cudnn/lib/libcudnn*.so.*"):
            for lib in sorted(glob.glob(os.path.join(sp, pattern))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def _device() -> tuple[str, str]:
    if WHISPER_DEVICE == "cpu":
        return "cpu", "int8"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def _load_wav(path: Path):
    """Read the 16 kHz mono PCM WAV that ingest.to_wav produces.
    Decoding it ourselves avoids faster-whisper's PyAV dependency, whose API drifts between versions."""
    import numpy as np

    with wave.open(str(path), "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("expected 16 kHz mono 16-bit WAV")
        pcm = w.readframes(w.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio: Path, on_progress: Callable[[float], None] | None = None) -> tuple[list[Segment], str]:
    _preload_cuda_libs()
    from faster_whisper import WhisperModel

    device, compute = _device()
    model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute)
    try:
        parts, info = model.transcribe(_load_wav(audio), vad_filter=True, beam_size=5)
        segments = []
        for p in parts:
            segments.append(Segment(start=p.start, end=p.end, text=p.text.strip()))
            if on_progress and info.duration:
                on_progress(min(1.0, p.end / info.duration))
        return segments, info.language
    finally:
        # Free VRAM before the LLM stage; both don't fit in 6 GB together.
        del model
        gc.collect()
