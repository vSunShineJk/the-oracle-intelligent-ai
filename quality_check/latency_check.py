import time
from typing import Callable

_emit_fn: Callable | None = None


def set_tracer(fn: Callable) -> None:
    global _emit_fn
    _emit_fn = fn


def trace(text: str, final: bool = False) -> None:
    if _emit_fn:
        _emit_fn(text, final)


def ms(start: float) -> str:
    return f"{(time.perf_counter() - start) * 1000:.0f}ms"


def sec(start: float) -> str:
    return f"{time.perf_counter() - start:.2f}s"
