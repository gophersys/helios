import threading
import time
from typing import Any, Optional

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def cache_get(key: str) -> Optional[Any]:
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            return None
        return value


def cache_set(key: str, value: Any, ttl_seconds: float = 5.0) -> None:
    with _lock:
        _cache[key] = (time.monotonic() + ttl_seconds, value)


def cache_delete(key: str) -> None:
    with _lock:
        _cache.pop(key, None)


def cache_clear() -> None:
    with _lock:
        _cache.clear()


def cached(key: str, ttl: float = 5.0):
    """Decorator that caches the return value of a function."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            result = cache_get(key)
            if result is not None:
                return result
            result = fn(*args, **kwargs)
            cache_set(key, result, ttl)
            return result
        return wrapper
    return decorator
