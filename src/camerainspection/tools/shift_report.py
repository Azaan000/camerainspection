"""CLI tool for end-of-shift quality report comparing camera vs human inspector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from sqlalchemy.orm import Session

from camerainspection.core.config import load_system_config
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    DefectRecord,
    HumanReviewRecord,
    SeatInspectionRecord,
    ShadowDecisionRecord,
)


def generate_shift_report_dict(
    session: Session,
    false_reject_threshold_pct: float = 3.0,
) -> dict:
    """Compute shift quality statistics comparing camera vs human inspector decisions."""
    seats = session.query(SeatInspectionRecord).all()
    total_inspected = len(seats)

    camera_pass = sum(1 for s in seats if s.outcome == "PASS")
    camera_review = sum(1 for s in seats if s.outcome == "REVIEW")
    camera_fail = sum(1 for s in seats if s.outcome == "FAIL")

    shadow_records = session.query(ShadowDecisionRecord).all()
    shadow_map = {r.seat_id: r.decision.upper() for r in shadow_records}

    # Also include resolved human reviews as human decisions
    human_reviews = session.query(HumanReviewRecord).filter_by(status="RESOLVED").all()
    for hr in human_reviews:
        if hr.seat_id not in shadow_map and hr.decision:
            shadow_map[hr.seat_id] = "PASS" if hr.decision.upper() == "PASS" else "FAIL"

    compared_seats = [s for s in seats if s.seat_id in shadow_map]
    n_compared = len(compared_seats)

    agreed = 0
    false_rejects = 0
    escapes = 0

    for s in compared_seats:
        cam_pass = (s.outcome == "PASS")
        human_pass = (shadow_map[s.seat_id] == "PASS")

        if cam_pass == human_pass:
            agreed += 1
        elif (not cam_pass) and human_pass:
            false_rejects += 1
        elif cam_pass and (not human_pass):
            escapes += 1

    agreement_rate = (agreed / n_compared) if n_compared > 0 else 1.0
    false_reject_rate = (false_rejects / n_compared) if n_compared > 0 else 0.0
    escape_rate = (escapes / n_compared) if n_compared > 0 else 0.0

    flagged_warning = (false_reject_rate * 100.0) > false_reject_threshold_pct

    # Per-defect breakdown
    defects = session.query(DefectRecord).all()
    defect_counts: dict[str, int] = {}
    for d in defects:
        defect_counts[d.defect_type] = defect_counts.get(d.defect_type, 0) + 1

    return {
        "total_inspected": total_inspected,
        "camera_pass_count": camera_pass,
        "camera_review_count": camera_review,
        "camera_fail_count": camera_fail,
        "human_decisions_count": len(shadow_map),
        "compared_sample_size": n_compared,
        "agreement_count": agreed,
        "agreement_rate": round(agreement_rate, 4),
        "false_reject_count": false_rejects,
        "false_reject_rate": round(false_reject_rate, 4),
        "escape_count": escapes,
        "escape_rate": round(escape_rate, 4),
        "threshold_pct": false_reject_threshold_pct,
        "flagged_false_reject_warning": flagged_warning,
        "defect_counts": defect_counts,
    }


def print_shift_report(data: dict) -> None:
    print("\n" + "=" * 65)
    print("      AUTOMATED INSPECTION - END-OF-SHIFT QUALITY REPORT")
    print("=" * 65)
    print(f"Total Seats Inspected:      {data['total_inspected']}")
    print(f"Camera PASS:                 {data['camera_pass_count']}")
    print(f"Camera REVIEW:               {data['camera_review_count']}")
    print(f"Camera FAIL:                 {data['camera_fail_count']}")
    print("-" * 65)
    print(f"Human Inspector Decisions:  {data['human_decisions_count']}")
    print(f"Direct Comparisons:         {data['compared_sample_size']}")
    print(f"Agreement Rate:             {data['agreement_rate'] * 100:.2f}%")
    print(f"False-Reject Rate:          {data['false_reject_rate'] * 100:.2f}% (Count: {data['false_reject_count']})")
    print(f"Escape Rate:                {data['escape_rate'] * 100:.2f}% (Count: {data['escape_count']})")
    print("-" * 65)

    if data["flagged_false_reject_warning"]:
        print(" [!] ALERT: False-Reject Rate exceeds limit threshold of "
              f"{data['threshold_pct']:.1f}%! Retune station tolerances or inspect camera lighting.")
    else:
        print(f" [OK] False-Reject Rate is within OEM acceptable band (<= {data['threshold_pct']:.1f}%).")

    if data.get("defect_counts"):
        print("\nTop Defect Types:")
        for dtype, cnt in sorted(data["defect_counts"].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {dtype:30s}: {cnt}")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Shift Report Quality Analytics CLI")
    parser.add_argument("--config", default="configs/system.yaml", help="Path to system config")
    parser.add_argument("--threshold", type=float, default=3.0, help="False-reject warning threshold percent")
    args = parser.parse_args()

    sys_cfg = load_system_config(Path(args.config))
    db = DatabaseManager(sys_cfg.database.url)

    with db.session_scope() as session:
        data = generate_shift_report_dict(session, false_reject_threshold_pct=args.threshold)
        print_shift_report(data)


if __name__ == "__main__":
    main()
