"""
Automated Backup System for SoundBox

Backs up generated audio files and database to dated directories.
Uses rsync with hardlinks to minimize disk usage.

Environment Variables:
    BACKUP_DIR: Base backup directory (required to enable backups)
    BACKUP_RETENTION_DAYS: Days to keep backups (default: 30)
    BACKUP_TIME: Time to run nightly backup in HH:MM format (default: 03:00)
"""

import os
import subprocess
import sqlite3
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "soundbox.db"
GENERATED_DIR = PROJECT_DIR / "generated"

# Backup state
_last_backup = {
    "time": None,
    "status": None,
    "size_mb": None,
    "error": None
}


def get_backup_dir():
    """Get backup directory from environment."""
    return os.environ.get("BACKUP_DIR")


def run_backup():
    """Run a full backup of the database and generated files."""
    backup_dir = get_backup_dir()
    if not backup_dir:
        logger.warning("BACKUP_DIR not set, skipping backup")
        return False

    backup_base = Path(backup_dir)
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = backup_base / today

    logger.info(f"Starting backup to {today_dir}")
    _last_backup["time"] = datetime.now().isoformat()
    _last_backup["status"] = "running"
    _last_backup["error"] = None

    try:
        # Create today's backup directory
        today_dir.mkdir(parents=True, exist_ok=True)

        # 1. Backup database using SQLite's backup command (safe while running)
        db_backup_path = today_dir / "soundbox.db"
        logger.info(f"Backing up database to {db_backup_path}")

        conn = sqlite3.connect(str(DB_PATH))
        backup_conn = sqlite3.connect(str(db_backup_path))
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        logger.info("Database backup complete")

        # 2. Find previous backup for hardlinking
        previous_backup = find_previous_backup(backup_base, today)

        # 3. Rsync generated files with hardlinks to previous backup
        generated_backup = today_dir / "generated"
        rsync_cmd = [
            "rsync", "-a", "--delete",
            str(GENERATED_DIR) + "/",
            str(generated_backup) + "/"
        ]

        if previous_backup:
            link_dest = previous_backup / "generated"
            if link_dest.exists():
                rsync_cmd.insert(2, f"--link-dest={link_dest}")
                logger.info(f"Using hardlinks from {previous_backup}")

        logger.info(f"Syncing generated files...")
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"rsync failed: {result.stderr}")
        logger.info("Generated files backup complete")

        # 4. Update 'latest' symlink
        latest_link = backup_base / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        elif latest_link.exists():
            shutil.rmtree(latest_link)
        latest_link.symlink_to(today_dir)
        logger.info(f"Updated 'latest' symlink to {today}")

        # 5. Calculate backup size
        size_mb = get_dir_size_mb(today_dir)
        _last_backup["size_mb"] = size_mb
        logger.info(f"Backup size: {size_mb:.1f} MB")

        # 6. Cleanup old backups
        cleanup_old_backups()

        _last_backup["status"] = "success"
        logger.info("Backup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        _last_backup["status"] = "error"
        _last_backup["error"] = str(e)
        return False


def find_previous_backup(backup_base: Path, exclude_date: str):
    """Find the most recent backup directory before today."""
    if not backup_base.exists():
        return None

    backups = []
    for item in backup_base.iterdir():
        if item.is_dir() and item.name != "latest" and item.name != exclude_date:
            try:
                # Validate it's a date directory
                datetime.strptime(item.name, "%Y-%m-%d")
                backups.append(item)
            except ValueError:
                continue

    if not backups:
        return None

    # Sort by name (date) descending
    backups.sort(key=lambda x: x.name, reverse=True)
    return backups[0]


def cleanup_old_backups():
    """
    Remove old backups with tiered retention:
    - Keep all daily backups for 14 days
    - Keep weekly backups (Sundays) for 2 more months
    - Delete everything older than ~74 days
    """
    backup_dir = get_backup_dir()
    if not backup_dir:
        return

    backup_base = Path(backup_dir)
    now = datetime.now()
    daily_cutoff = now - timedelta(days=14)
    weekly_cutoff = now - timedelta(days=74)  # 14 days + 2 months

    logger.info("Cleaning up old backups (14 days daily, then weekly for 2 months)")

    removed = 0
    for item in backup_base.iterdir():
        if item.is_dir() and item.name != "latest":
            try:
                backup_date = datetime.strptime(item.name, "%Y-%m-%d")

                # Keep all backups less than 14 days old
                if backup_date >= daily_cutoff:
                    continue

                # For backups 14-74 days old, keep only Sundays (weekday 6)
                if backup_date >= weekly_cutoff:
                    if backup_date.weekday() == 6:  # Sunday
                        continue
                    # Delete non-Sunday backups older than 14 days
                    logger.info(f"Removing non-weekly backup: {item.name}")
                    shutil.rmtree(item)
                    removed += 1
                else:
                    # Delete everything older than 74 days
                    logger.info(f"Removing old backup: {item.name}")
                    shutil.rmtree(item)
                    removed += 1

            except ValueError:
                continue

    if removed:
        logger.info(f"Removed {removed} old backup(s)")


def get_dir_size_mb(path: Path):
    """Calculate directory size in megabytes."""
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total / (1024 * 1024)


def get_backup_status():
    """Get status of backup system for API."""
    backup_dir = get_backup_dir()

    status = {
        "enabled": backup_dir is not None,
        "backup_dir": backup_dir,
        "retention_policy": "14 days daily, then weekly for 2 months",
        "backup_time": os.environ.get("BACKUP_TIME", "03:00"),
        "last_backup": _last_backup.copy()
    }

    if backup_dir:
        backup_base = Path(backup_dir)
        if backup_base.exists():
            # Count existing dated backups (YYYY-MM-DD format only)
            backups = []
            for d in backup_base.iterdir():
                if d.is_dir() and d.name != "latest":
                    try:
                        datetime.strptime(d.name, "%Y-%m-%d")
                        backups.append(d)
                    except ValueError:
                        continue

            status["backup_count"] = len(backups)

            # Get latest backup date
            if backups:
                backups.sort(key=lambda x: x.name, reverse=True)
                status["latest_backup_date"] = backups[0].name

    return status


if __name__ == "__main__":
    # Allow running directly for testing
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        import json
        print(json.dumps(get_backup_status(), indent=2))
    else:
        if not get_backup_dir():
            print("Error: BACKUP_DIR environment variable not set")
            print("Usage: BACKUP_DIR=/path/to/backups python backup.py")
            sys.exit(1)

        success = run_backup()
        sys.exit(0 if success else 1)
