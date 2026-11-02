"""Bound ONNX Runtime to a fixed number of CPU threads.

onnxruntime defaults to one thread per core for every session. On a 2-core
container that also runs BookOrbit, that default uses the whole CPU budget.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_warned_unlimited = False


def limit_onnx_threads(threads: int) -> None:
    global _warned_unlimited
    if threads <= 0:
        if not _warned_unlimited:
            log.warning(
                "BOOKORBIT_TTS_THREADS=%s lets ONNX Runtime use every visible core",
                threads,
            )
            _warned_unlimited = True
        return
    # Set these before the first onnxruntime import. A library that has already
    # read them keeps its own pool; the session options below still cover Piper.
    for variable in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(variable, str(threads))
    try:
        import onnxruntime as ort
    except ImportError:  # pragma: no cover - piper pulls onnxruntime in
        return
    if getattr(ort, "_bookorbit_limit_applied", False):
        return

    original = ort.InferenceSession

    def patched(path_or_bytes, sess_options=None, providers=None, **kwargs):
        options = sess_options if sess_options is not None else ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        if hasattr(ort, "ExecutionMode"):
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        # The memory pattern cache speeds repeated shapes and costs RAM we
        # would rather leave for BookOrbit. Sentence length varies anyway.
        options.enable_mem_pattern = False
        if providers is None:
            # Passing providers=None is not the same as omitting it: some
            # onnxruntime builds then fail to enable the CPU provider.
            return original(path_or_bytes, sess_options=options, **kwargs)
        return original(path_or_bytes, sess_options=options, providers=providers, **kwargs)

    patched.__doc__ = original.__doc__
    ort.InferenceSession = patched
    ort._bookorbit_limit_applied = True
    log.info("onnxruntime limited to %d thread(s)", threads)
