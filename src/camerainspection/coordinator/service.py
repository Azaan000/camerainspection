"""Inspection Coordinator orchestrating multi-station aggregation and label gating."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from camerainspection.core.logging import get_logger
from camerainspection.core.models import (
    Outcome,
    OverallSeatInspectionResult,
    StationInspectionResult,
)
from camerainspection.hardware.plc.base import BasePLC
from camerainspection.storage.db import DatabaseManager

logger = get_logger("coordinator")

_DEFAULT_CYCLE_TIMEOUT_S = 60.0
_DEFAULT_PRINT_PULSE_TIMEOUT_S = 5.0


class InspectionCoordinator:
    """Aggregates results across inspection stations and coordinates line interlocks.

    Safety interlocks:
    - Label printer enabled ONLY when ALL expected stations pass AND mechanism cycle test
      passes AND lock sensor is confirmed.
    - Per-seat tracking for label printing so new pallet arrivals don't prematurely abort printing of a finalized seat.
    - When a new seat arrives or any station reports FAIL/REVIEW, printer output is immediately disabled.
    - Background watchdog thread continuously enforces cycle_timeout_s and print_pulse_timeout_s.
    - Seats that do not fully report within ``cycle_timeout_s`` are auto-finalised as FAIL.
    """

    def __init__(
        self,
        plc: BasePLC,
        db_manager: DatabaseManager,
        expected_stations: list[str] | None = None,
        shadow_mode: bool = False,
        cycle_timeout_s: float = _DEFAULT_CYCLE_TIMEOUT_S,
        print_pulse_timeout_s: float = _DEFAULT_PRINT_PULSE_TIMEOUT_S,
        enable_watchdog: bool = True,
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
        self.cycle_timeout_s = cycle_timeout_s
        self.print_pulse_timeout_s = print_pulse_timeout_s
        self._lock = threading.Lock()

        # In-memory buffer of partial station results keyed by seat_id
        # {seat_id: {station_id: StationInspectionResult}}
        self._seat_buffers: dict[str, dict[str, StationInspectionResult]] = {}
        self._seat_variants: dict[str, str] = {}
        self._seat_first_seen: dict[str, datetime] = {}

        # Per-seat printer enablement state tracking
        self._seat_printer_eligible: dict[str, bool] = {}
        self._seat_print_time: dict[str, datetime] = {}
        self._currently_printing_seat_id: str | None = None

        # Background watchdog timer thread
        self._running = True
        self._watchdog_thread: threading.Thread | None = None
        if enable_watchdog:
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="coordinator-watchdog"
            )
            self._watchdog_thread.start()

    def shutdown(self) -> None:
        """Stop watchdog thread cleanly."""
        self._running = False
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=1.0)

    def _watchdog_loop(self) -> None:
        """Background thread checking for cycle timeouts and printer auto-disable every 0.5s."""
        while self._running:
            try:
                with self._lock:
                    self._purge_timed_out_seats_unlocked()
                    self._enforce_printer_timeout_unlocked()
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
            time.sleep(0.5)

    def _enforce_printer_timeout_unlocked(self) -> None:
        """Auto-disable printer pulse if duration exceeds print_pulse_timeout_s."""
        if self._currently_printing_seat_id is not None:
            now = datetime.now(UTC)
            t = self._seat_print_time.get(self._currently_printing_seat_id)
            if t and (now - t).total_seconds() >= self.print_pulse_timeout_s:
                sid = self._currently_printing_seat_id
                logger.info(
                    f"Print pulse window ({self.print_pulse_timeout_s}s) elapsed for {sid}. Disabling printer."
                )
                self._currently_printing_seat_id = None
                self._seat_print_time.pop(sid, None)
                self._seat_printer_eligible.pop(sid, None)
                if not self.shadow_mode and self.plc is not None:
                    self.plc.set_label_printer_enable(False)
                    self.plc.clear_seat(sid)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_station_result(
        self, res: StationInspectionResult
    ) -> OverallSeatInspectionResult | None:
        """Register an incoming result from a station.

        Returns:
            OverallSeatInspectionResult if all expected stations have reported for the seat,
            otherwise None (waiting for remaining stations).
        """
        with self._lock:
            seat_id = res.seat_id
            is_new_seat = seat_id not in self._seat_buffers

            if is_new_seat:
                self._seat_buffers[seat_id] = {}
                self._seat_variants[seat_id] = res.variant_id
                self._seat_first_seen[seat_id] = datetime.now(UTC)
                self._seat_printer_eligible[seat_id] = False

                # Crucial safety rule: Disable printer as soon as a new seat arrives / starts inspection
                if self._currently_printing_seat_id is not None:
                    logger.info(
                        f"New seat {seat_id} entered line. Shutting off printer previously enabled "
                        f"for {self._currently_printing_seat_id}."
                    )
                    self._seat_printer_eligible.pop(self._currently_printing_seat_id, None)
                    self._seat_print_time.pop(self._currently_printing_seat_id, None)
                    self._currently_printing_seat_id = None
                if not self.shadow_mode and self.plc is not None:
                    self.plc.set_label_printer_enable(False)

            self._seat_buffers[seat_id][res.station_id] = res

            # Reflect station outcome into PLC tags with seat_id awareness
            if not self.shadow_mode and self.plc is not None:
                self.plc.set_station_result(res.station_id, res.outcome, seat_id=seat_id)

            # If station result is FAIL or REVIEW, ensure printer is off
            if res.outcome in (Outcome.FAIL, Outcome.REVIEW):
                if not self.shadow_mode and self.plc is not None:
                    self.plc.set_label_printer_enable(False)
                if self._currently_printing_seat_id == seat_id:
                    self._currently_printing_seat_id = None

            # Check if all expected stations reported for this seat
            reported_stations = set(self._seat_buffers[seat_id].keys())
            expected_set = set(self.expected_stations)

            if expected_set.issubset(reported_stations):
                return self._finalize_seat_unlocked(seat_id)

            return None

    def mark_seat_printed(self, seat_id: str) -> None:
        """Called when physical applicator has applied label for seat_id."""
        with self._lock:
            if self._currently_printing_seat_id == seat_id:
                self._currently_printing_seat_id = None
            self._seat_printer_eligible.pop(seat_id, None)
            self._seat_print_time.pop(seat_id, None)
            if not self.shadow_mode and self.plc is not None:
                self.plc.set_label_printer_enable(False)
                self.plc.clear_seat(seat_id)
            logger.info(f"Seat {seat_id} label applied. Printer output disabled and tracking cleared.")

    def finalize_seat(self, seat_id: str) -> OverallSeatInspectionResult:
        """Manually force completion of a seat inspection cycle (e.g. on timeout)."""
        with self._lock:
            return self._finalize_seat_unlocked(seat_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_timed_out_seats_unlocked(self, exclude: str | None = None) -> None:
        """Auto-finalise any seats whose cycle has exceeded ``cycle_timeout_s``."""
        now = datetime.now(UTC)
        timed_out = [
            sid
            for sid, first_seen in list(self._seat_first_seen.items())
            if sid != exclude and (now - first_seen).total_seconds() >= self.cycle_timeout_s
        ]
        for sid in timed_out:
            logger.warning(
                f"Seat {sid} exceeded cycle timeout ({self.cycle_timeout_s}s). "
                "Auto-finalising as FAIL."
            )
            try:
                self.db.log_audit(
                    event_type="CYCLE_TIMEOUT",
                    details=(
                        f"Seat {sid} timed out after {self.cycle_timeout_s}s. "
                        f"Reported stations: {list(self._seat_buffers.get(sid, {}).keys())}"
                    ),
                    seat_id=sid,
                )
            except Exception as e:
                logger.error(f"Failed to log CYCLE_TIMEOUT audit event for {sid}: {e}")
            self._finalize_seat_unlocked(sid)

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
        # Strict Rule: OEM label printer may ONLY be enabled when EVERY station PASSES,
        # the mechanism cycle test PASSES, AND the lock sensor is confirmed.
        all_stations_pass = (
            overall_outcome == Outcome.PASS
            and not missing_stations
            and all(r.outcome == Outcome.PASS for r in results.values())
        )
        can_enable_printer = all_stations_pass and mech_passed and lock_confirmed

        if can_enable_printer:
            self._seat_printer_eligible[seat_id] = True
            self._currently_printing_seat_id = seat_id
            self._seat_print_time[seat_id] = datetime.now(UTC)
            if not self.shadow_mode and self.plc is not None:
                self.plc.set_label_printer_enable(True, seat_id=seat_id)
        else:
            self._seat_printer_eligible.pop(seat_id, None)
            self._seat_print_time.pop(seat_id, None)
            # Crucial: On ANY non-passing finalization, immediately disable printer
            self._currently_printing_seat_id = None
            if not self.shadow_mode and self.plc is not None:
                self.plc.set_label_printer_enable(False)
                if overall_outcome == Outcome.FAIL:
                    self.plc.clear_seat(seat_id)

        overall = OverallSeatInspectionResult(
            seat_id=seat_id,
            variant_id=variant_id,
            outcome=overall_outcome,
            station_results=dict(results),
            mechanism_cycle_passed=mech_passed,
            lock_sensor_confirmed=lock_confirmed,
            label_printer_enabled=can_enable_printer,
            shadow_mode=self.shadow_mode,
            timestamp=datetime.now(UTC),
        )

        # 4. Persist to database
        try:
            self.db.record_overall_result(overall)
            if overall_outcome == Outcome.REVIEW:
                self.db.queue_for_review(seat_id)
            elif self.shadow_mode:
                # In shadow mode, human audit queue samples PASS seats as well for escape tracking
                self.db.queue_for_review(seat_id)

            self.db.log_audit(
                event_type="OVERALL_INSPECTION_FINALIZED",
                details=(
                    f"Seat: {seat_id}, Outcome: {overall_outcome.value}, "
                    f"LabelPrinter: {can_enable_printer}, LockConfirmed: {lock_confirmed}, "
                    f"MechPassed: {mech_passed}, "
                    f"Stations: {list(results.keys())}"
                ),
                seat_id=seat_id,
            )
        except Exception as e:
            logger.error(f"Failed to persist overall result to DB for {seat_id}: {e}")

        # Clean buffer
        self._seat_buffers.pop(seat_id, None)
        self._seat_variants.pop(seat_id, None)
        self._seat_first_seen.pop(seat_id, None)

        return overall
