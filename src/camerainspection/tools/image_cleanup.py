"""Image retention cleanup — deletes capture folders older than the configured retention period.

Usage (CLI):
    python -m camerainspection.tools.image_cleanup --days 30 --dry-run
    python -m camerainspection.tools.image_cleanup --days 30

Called automatically by the API endpoint POST /api/v1/system/cleanup-images.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CAPTURES_ROOT = Path("storage/captures")


def cleanup_old_captures(
    retention_days: int = 0,
    captures_root: Path = CAPTURES_ROOT,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    """Delete seat capture folders whose newest file is older than retention_days.

    Returns a summary dict with keys:
      - deleted_folders: int
      - freed_mb: float
      - deleted_paths: list[str]
      - skipped: int
      - errors: list[str]
    """
    if retention_days < 0:
        raise ValueError(f"retention_days must be >= 0, got {retention_days}")

    cutoff_ts = time.time() - retention_days * 86400
    cutoff_dt = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc)

    deleted_folders = 0
    freed_bytes = 0
    deleted_paths: list[str] = []
    skipped = 0
    errors: list[str] = []

    if not captures_root.exists():
        logger.info("Captures root %s does not exist — nothing to clean", captures_root)
        return {
            "deleted_folders": 0,
            "freed_mb": 0.0,
            "deleted_paths": [],
            "skipped": 0,
            "errors": [],
            "cutoff_date": cutoff_dt.isoformat(),
        }

    for seat_dir in sorted(captures_root.iterdir()):
        if not seat_dir.is_dir():
            continue

        # Find the newest file modification time in this seat folder
        try:
            all_files = list(seat_dir.rglob("*"))
            if not all_files:
                # Empty folder — delete it
                newest_mtime = 0.0
            else:
                newest_mtime = max(f.stat().st_mtime for f in all_files if f.is_file())
        except Exception as exc:
            errors.append(f"{seat_dir.name}: stat error — {exc}")
            skipped += 1
            continue

        if newest_mtime > cutoff_ts:
            skipped += 1
            continue

        # Calculate folder size before deleting
        try:
            folder_bytes = sum(
                f.stat().st_size for f in seat_dir.rglob("*") if f.is_file()
            )
        except Exception:
            folder_bytes = 0

        age_days = (time.time() - newest_mtime) / 86400
        logger.info(
            "%s %s (%.0f days old, %.1f MB)",
            "[DRY RUN] Would delete" if dry_run else "Deleting",
            seat_dir.name,
            age_days,
            folder_bytes / 1e6,
        )

        if not dry_run:
            try:
                # Remove read-only attribute if present on Windows
                for f in seat_dir.rglob("*"):
                    try:
                        f.chmod(0o777)
                    except Exception:
                        pass
                shutil.rmtree(seat_dir, ignore_errors=True)
                deleted_folders += 1
                freed_bytes += folder_bytes
                deleted_paths.append(seat_dir.name)
            except Exception as exc:
                errors.append(f"{seat_dir.name}: delete error — {exc}")
                skipped += 1
        else:
            deleted_folders += 1
            freed_bytes += folder_bytes
            deleted_paths.append(seat_dir.name)

    logger.info(
        "Cleanup complete: %d folders %s, %.1f MB freed, %d skipped, %d errors",
        deleted_folders,
        "would be deleted" if dry_run else "deleted",
        freed_bytes / 1e6,
        skipped,
        len(errors),
    )

    return {
        "deleted_folders": deleted_folders,
        "freed_mb": round(freed_bytes / 1e6, 2),
        "deleted_paths": deleted_paths,
        "skipped": skipped,
        "errors": errors,
        "cutoff_date": cutoff_dt.isoformat(),
        "dry_run": dry_run,
    }


def get_storage_stats(captures_root: Path = CAPTURES_ROOT) -> dict:
    """Return current storage usage stats for the captures directory."""
    if not captures_root.exists():
        return {"total_mb": 0.0, "total_folders": 0, "total_files": 0, "oldest_days": None}

    total_bytes = 0
    total_folders = 0
    total_files = 0
    oldest_mtime = float("inf")

    for seat_dir in captures_root.iterdir():
        if not seat_dir.is_dir():
            continue
        total_folders += 1
        for f in seat_dir.rglob("*"):
            if f.is_file():
                try:
                    st = f.stat()
                    total_bytes += st.st_size
                    total_files += 1
                    if st.st_mtime < oldest_mtime:
                        oldest_mtime = st.st_mtime
                except Exception:
                    pass

    oldest_days = None
    if oldest_mtime != float("inf"):
        oldest_days = round((time.time() - oldest_mtime) / 86400, 1)

    return {
        "total_mb": round(total_bytes / 1e6, 2),
        "total_folders": total_folders,
        "total_files": total_files,
        "oldest_days": oldest_days,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Clean up old seat capture images")
    parser.add_argument("--days", type=int, default=30, help="Retention period in days")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--root", default="storage/captures", help="Captures root directory")
    args = parser.parse_args()

    result = cleanup_old_captures(
        retention_days=args.days,
        captures_root=Path(args.root),
        dry_run=args.dry_run,
    )
    print(f"\nResult: {result['deleted_folders']} folders {'(dry run) ' if result.get('dry_run') else ''}deleted")
    print(f"Freed  : {result['freed_mb']} MB")
    if result["errors"]:
        print(f"Errors : {result['errors']}")
