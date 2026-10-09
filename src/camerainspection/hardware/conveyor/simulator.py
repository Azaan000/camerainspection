"""Software simulator for line conveyor and reject spur."""

from __future__ import annotations

from camerainspection.hardware.conveyor.base import BaseConveyor


class ConveyorSimulator(BaseConveyor):
    """Simulator tracking conveyor status and diverted reject seats."""

    def __init__(self) -> None:
        self._running: bool = False
        self._diverted_seats: list[str] = []
        self._mainline_seats: list[str] = []

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> bool:
        self._running = False
        return True

    def is_running(self) -> bool:
        return self._running

    def divert_to_reject(self, seat_id: str) -> bool:
        self._diverted_seats.append(seat_id)
        return True

    def release_to_mainline(self, seat_id: str) -> bool:
        self._mainline_seats.append(seat_id)
        return True

    @property
    def diverted_seats(self) -> list[str]:
        return list(self._diverted_seats)

    @property
    def mainline_seats(self) -> list[str]:
        return list(self._mainline_seats)
