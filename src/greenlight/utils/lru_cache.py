"""Thread-safe LRU cache keyed by text hash."""

import threading
from collections import OrderedDict
from typing import Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Tiny LRU cache for use by request handlers."""

    def __init__(self, maxsize: int = 256) -> None:
        self._data: OrderedDict[K, V] = OrderedDict()
        self._max = maxsize
        self._lock = threading.Lock()

    def get_or_compute(self, key: K, compute: Callable[[], V]) -> V:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        value = compute()
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            self._data[key] = value
            while len(self._data) > self._max:
                self._data.popitem(last=False)
        return value

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
