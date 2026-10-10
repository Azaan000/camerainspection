"""Unit tests for RFID readers, Conveyor diverter, Operator Panel, and Acceptance test harness."""

from __future__ import annotations

from camerainspection.hardware.conveyor.factory import build_conveyor
from camerainspection.hardware.conveyor.simulator import ConveyorSimulator
from camerainspection.hardware.operator_panel.factory import build_operator_panel
from camerainspection.hardware.operator_panel.simulator import OperatorPanelSimulator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.rfid.factory import build_rfid_reader
from camerainspection.hardware.rfid.simulator import RFIDSimulator
from camerainspection.tools.acceptance_test import run_acceptance_test


def test_rfid_simulator_lifecycle() -> None:
    reader = build_rfid_reader({"adapter": "simulator", "initial_tag": "SEAT_TAG_101"})
    assert isinstance(reader, RFIDSimulator)
    assert reader.is_connected() is True

    # Read tag
    assert reader.read_tag() == "SEAT_TAG_101"

    # Enqueue tags
    reader.enqueue_tags(["SEAT_TAG_102", "SEAT_TAG_103"])
    assert reader.read_tag() == "SEAT_TAG_102"
    assert reader.read_tag() == "SEAT_TAG_103"

    # Write tag
    assert reader.write_tag("SEAT_TAG_104") is True
    assert reader.read_tag() == "SEAT_TAG_104"

    # Simulate failure
    reader.set_failure_mode(True)
    assert reader.is_connected() is False
    assert reader.read_tag() is None


def test_conveyor_and_reject_diverter() -> None:
    conv = build_conveyor({"adapter": "simulator"})
    assert isinstance(conv, ConveyorSimulator)

    assert conv.is_running() is False
    conv.start()
    assert conv.is_running() is True

    # Divert reject
    conv.divert_to_reject("DEFECT_SEAT_1")
    assert "DEFECT_SEAT_1" in conv.diverted_seats

    # Release mainline
    conv.release_to_mainline("PASS_SEAT_1")
    assert "PASS_SEAT_1" in conv.mainline_seats

    conv.stop()
    assert conv.is_running() is False


def test_operator_panel_simulator() -> None:
    panel = build_operator_panel({"adapter": "simulator"})
    assert isinstance(panel, OperatorPanelSimulator)

    # Pushbuttons momentary reads
    panel.press_start()
    assert panel.read_start() is True
    assert panel.read_start() is False  # Momentary cleared

    panel.press_stop()
    assert panel.read_stop() is True
    assert panel.read_stop() is False

    panel.press_reset()
    assert panel.read_reset() is True
    assert panel.read_reset() is False

    # E-Stop maintained contact
    assert panel.read_e_stop() is False
    panel.trigger_e_stop(True)
    assert panel.read_e_stop() is True
    assert panel.read_e_stop() is True
    panel.trigger_e_stop(False)
    assert panel.read_e_stop() is False

    # Indicators
    panel.set_indicator("green", True)
    assert panel.get_indicator("green") is True
    panel.set_indicator("green", False)
    assert panel.get_indicator("green") is False


def test_plc_backed_conveyor_and_panel() -> None:
    plc = PLCSimulator()
    plc.connect()

    conv = build_conveyor({"adapter": "plc"}, plc=plc)
    assert conv.start() is True
    assert conv.divert_to_reject("FAIL_01") is True
    assert conv.release_to_mainline("PASS_01") is True

    panel = build_operator_panel({"adapter": "plc"}, plc=plc)
    assert panel.read_start() is False
    assert panel.read_stop() is False
    panel.set_indicator("amber", True)


def test_acceptance_test_harness_execution() -> None:
    """Run automated acceptance test suite in unit test."""
    ok = run_acceptance_test(num_clean_seats=10)
    assert ok is True
