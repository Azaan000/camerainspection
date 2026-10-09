"""Simulated RFID transponder reader for testing and development."""

from __future__ import annotations

import collections
import time
from camerainspection.hardware.rfid.base import BaseRFIDReader


class RFIDSimulator(BaseRFIDReader):
    """Software simulation of an industrial RFID reader."""

    def __init__(self, initial_tag: str | None = None) -> None:
        self._connected: bool = True
        self._current_tag: str | None = initial_tag
        self._tag_queue: collections.deque[str] = collections.deque()
        self._simulate_failure: bool = False

    def connect(self) -> bool:
        if self._simulate_failure:
            self._connected = False
            return False
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and not self._simulate_failure

    def read_tag(self, timeout_s: float = 1.0) -> str | None:
        if not self.is_connected():
            return None
        if self._tag_queue:
            self._current_tag = self._tag_queue.popleft()
        return self._current_tag

    def write_tag(self, tag_id: str, timeout_s: float = 1.0) -> bool:
        if not self.is_connected():
            return False
        self._current_tag = tag_id
        return True

    # Simulation control helpers
    def set_current_tag(self, tag_id: str | None) -> None:
        """Manually place a tag into the reader RF field."""
        self._current_tag = tag_id

    def enqueue_tags(self, tags: list[str]) -> None:
        """Enqueue multiple tags to simulate seats arriving sequentially."""
        self._tag_queue.extend(tags)

    def set_failure_mode(self, fail: bool) -> None:
        """Simulate hardware communication disconnection or antenna fault."""
        self._simulate_failure = fail
