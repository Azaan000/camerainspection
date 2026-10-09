"""Inspection Coordinator orchestrating multi-station aggregation and label gating."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import (
    Outcome,
    OverallSeatInspectionResult,
    StationInspectionResult,
)
from camerainspection.hardware.plc.base import BasePLC
from camerainspection.storage.db import DatabaseManager

logger = get_logger("coordinator")


class InspectionCoordinator:
    """Aggregates results across inspection stations and coordinates line interlocks.

    Safety interlocks:
    - Label printer enabled ONLY when ALL expected stations pass AND mechanism lock is confirmed.
    - Fails safe if any station reports FAIL or REVIEW, or if a station times out / missing.
    - Respects shadow mode (logs decisions without driving physical PLC outputs).
    """

    def __init__(
        self,
        plc: BasePLC,
        db_manager: DatabaseManager,
        expected_stations: list[str] | None = None,
        shadow_mode: bool = False,
    ) -> None:
        self.plc = plc
        self.db = db_manager
        self.expected_stations = expected_stations or [
            "STATION_1",
            "STATION_2",
            "STATION_3",
            "STATION_4",
        ]
        self.shadow_mode = shadow_mode
        self._lock = threading.Lock()

        # In-memory buffer of partial station results keyed by seat_id
        # {seat_id: {station_id: StationInspectionResult}}
        self._seat_buffers: dict[str, dict[str, StationInspectionResult]] = {}
        self._seat_variants: dict[str, str] = {}

    def register_station_result(self, res: StationInspectionResult) -> OverallSeatInspectionResult | None:
        """Register an incoming result from a station.

        Returns:
            OverallSeatInspectionResult if all expected stations have reported for the seat,
            otherwise None (waiting for remaining stations).
        """
        with self._lock:
            seat_id = res.seat_id
            if seat_id not in self._seat_buffers:
                self._seat_buffers[seat_id] = {}
                self._seat_variants[seat_id] = res.variant_id

            self._seat_buffers[seat_id][res.station_id] = res

            # Reflect station outcome into PLC simulator tags
            if not self.shadow_mode and self.plc is not None:
                self.plc.set_station_result(res.station_id, res.outcome)

            # Check if all expected stations reported
            reported_stations = set(self._seat_buffers[seat_id].keys())
            expected_set = set(self.expected_stations)

            if expected_set.issubset(reported_stations):
                return self._finalize_seat_unlocked(seat_id)

            return None

    def finalize_seat(self, seat_id: str) -> OverallSeatInspectionResult:
        """Manually force completion of a seat inspection cycle (e.g. on timeout)."""
        with self._lock:
            return self._finalize_seat_unlocked(seat_id)

    def _finalize_seat_unlocked(self, seat_id: str) -> OverallSeatInspectionResult:
        """Internal helper evaluating overall seat status and driving interlocks."""
        results = self._seat_buffers.get(seat_id, {})
        variant_id = self._seat_variants.get(seat_id, "UNKNOWN")

        # 1. Aggregate station outcomes
        missing_stations = [st for st in self.expected_stations if st not in results]
        outcomes = [r.outcome for r in results.values()]

        if missing_stations:
            logger.warning(
                f"Seat {seat_id} finalizing with missing stations: {missing_stations}. Failing safe."
            )
            outcomes.append(Outcome.FAIL)

        overall_outcome = Outcome.aggregate(outcomes)

        # 2. Check mechanism status from station 4 if available, and verify PLC lock sensor
        st4_res = results.get("STATION_4")
        mech_passed = (
            st4_res is not None
            and st4_res.outcome == Outcome.PASS
            and "recliner_angle_deg" in st4_res.measurements
        )

        lock_confirmed = self.plc.is_mechanism_locked() if self.plc is not None else False

        # 3. Label printer interlock
        # Strict Rule: OEM label printer may ONLY be enabled when EVERY station and the
        # mechanism cycle test PASS and lock sensor is confirmed.
        all_stations_pass = (
            overall_outcome == Outcome.PASS
            and not missing_stations
            and all(r.outcome == Outcome.PASS for r in results.values())
        )
        can_enable_printer = all_stations_pass and lock_confirmed

        if not self.shadow_mode and self.plc is not None:
            self.plc.set_label_printer_enable(can_enable_printer)
        else:
            logger.info(
                f"Shadow mode: label printer enable={can_enable_printer} computed without driving PLC."
            )

        overall = OverallSeatInspectionResult(
            seat_id=seat_id,
            variant_id=variant_id,
            outcome=overall_outcome,
            station_results=dict(results),
            mechanism_cycle_passed=mech_passed,
            lock_sensor_confirmed=lock_confirmed,
            label_printer_enabled=can_enable_printer,
            shadow_mode=self.shadow_mode,
            timestamp=datetime.now(timezone.utc),
        )

        # 4. Persist to database
        try:
            self.db.record_overall_result(overall)
            if overall_outcome == Outcome.REVIEW:
                self.db.queue_for_review(seat_id)
            self.db.log_audit(
                event_type="OVERALL_INSPECTION_FINALIZED",
                details=(
                    f"Seat: {seat_id}, Outcome: {overall_outcome.value}, "
                    f"LabelPrinter: {can_enable_printer}, LockConfirmed: {lock_confirmed}, "
                    f"Stations: {list(results.keys())}"
                ),
                seat_id=seat_id,
            )
        except Exception as e:
            logger.error(f"Failed to persist overall result to DB for {seat_id}: {e}")

        # Clean buffer
        self._seat_buffers.pop(seat_id, None)
        self._seat_variants.pop(seat_id, None)

        return overall
