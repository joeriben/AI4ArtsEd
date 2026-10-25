"""
Legacy Export Folder Migration Tool

Migrates legacy export folders from flat structure to new session-based structure:
- OLD: exports/json/{random_folder_name}/
- NEW: exports/json/YYYY-MM-DD/legacy_YYYYMMDD/{original_folder_name}/

This tool is FAILSAFE and idempotent - safe to run multiple times.
"""

import json
import logging
import re
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    """Results from a migration run."""
    total_found: int = 0
    migrated: int = 0
    already_migrated: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[Tuple[str, str]] = None  # [(folder_name, error_msg), ...]

    def __post_init__(self):
        if self.error_details is None:
            self.error_details = []


def is_legacy_folder(folder_name: str) -> bool:
    """
    Check if a folder name is legacy (not in new YYYY-MM-DD format).

    NEW folders match: YYYY-MM-DD (exactly)
    LEGACY folders: Everything else (UUIDs, run_*, any other format)

    Args:
        folder_name: Name of the folder to check

    Returns:
        True if legacy, False if new format
    """
    # New format is exactly YYYY-MM-DD
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    return not re.match(date_pattern, folder_name)


def get_date_from_metadata(folder_path: Path) -> Optional[str]:
    """
    Extract date from metadata.json timestamp field.

    Args:
        folder_path: Path to the folder containing metadata.json

    Returns:
        Date string in YYYY-MM-DD format, or None if not found
    """
    metadata_file = folder_path / "metadata.json"

    if not metadata_file.exists():
        return None

    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Try to get timestamp field
        timestamp = metadata.get('timestamp')
        if not timestamp:
            return None

        # Parse timestamp (format: "YYYY-MM-DD HH:MM:SS" or ISO format)
        if isinstance(timestamp, str):
            # Try to parse various formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    dt = datetime.strptime(timestamp.split('.')[0], fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Could not read metadata from {folder_path}: {e}")
        return None


def get_date_from_filesystem(folder_path: Path) -> str:
    """
    Get date from filesystem modification time as fallback.

    Args:
        folder_path: Path to the folder

    Returns:
        Date string in YYYY-MM-DD format
    """
    try:
        mtime = folder_path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime("%Y-%m-%d")
    except OSError:
        # Ultimate fallback: today's date
        return datetime.now().strftime("%Y-%m-%d")


def migrate_single_folder(
    source_folder: Path,
    base_path: Path,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Migrate a single legacy folder to the new structure.

    Args:
        source_folder: Path to the legacy folder
        base_path: Base path (exports/json/)
        dry_run: If True, only simulate the migration

    Returns:
        Tuple of (success: bool, message: str)
    """
    folder_name = source_folder.name

    # Extract date from metadata or filesystem
    date_str = get_date_from_metadata(source_folder)
    if not date_str:
        date_str = get_date_from_filesystem(source_folder)

    # Create device_id from date (legacy_YYYYMMDD)
    device_id = f"legacy_{date_str.replace('-', '')}"

    # Build target path: YYYY-MM-DD/legacy_YYYYMMDD/{original_name}/
    target_path = base_path / date_str / device_id / folder_name

    # Check if already migrated (target exists)
    if target_path.exists():
        return True, f"Already migrated: {folder_name} -> {target_path.relative_to(base_path)}"

    if dry_run:
        return True, f"[DRY RUN] Would migrate: {folder_name} -> {target_path.relative_to(base_path)}"

    try:
        # Create parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Move folder (FAILSAFE: shutil.move does not delete source on error)
        shutil.move(str(source_folder), str(target_path))

        return True, f"Migrated: {folder_name} -> {target_path.relative_to(base_path)}"
    except Exception as e:
        error_msg = f"Error migrating {folder_name}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def run_migration(
    base_path: Path,
    dry_run: bool = False,
    max_folders: Optional[int] = None,
    progress_callback: Optional[callable] = None
) -> MigrationResult:
    """
    Run migration on all legacy folders in base_path.

    Args:
        base_path: Base path (exports/json/)
        dry_run: If True, only simulate the migration
        max_folders: Maximum number of folders to process (for testing)
        progress_callback: Optional callback function(current, total) for progress updates

    Returns:
        MigrationResult with statistics
    """
    result = MigrationResult()

    if not base_path.exists():
        logger.warning(f"Base path does not exist: {base_path}")
        return result

    # Find all legacy folders
    legacy_folders = []
    try:
        for item in base_path.iterdir():
            if item.is_dir() and is_legacy_folder(item.name):
                legacy_folders.append(item)
    except OSError as e:
        logger.error(f"Error scanning base path: {e}")
        return result

    result.total_found = len(legacy_folders)

    if result.total_found == 0:
        logger.info("[MIGRATION] No legacy folders found - migration complete")
        return result

    # Apply max_folders limit if specified
    if max_folders:
        legacy_folders = legacy_folders[:max_folders]

    # Process each folder
    for idx, folder in enumerate(legacy_folders, 1):
        success, message = migrate_single_folder(folder, base_path, dry_run)

        if success:
            if "Already migrated" in message:
                result.already_migrated += 1
            else:
                result.migrated += 1
                logger.debug(message)
        else:
            result.errors += 1
            result.error_details.append((folder.name, message))

        # Progress callback
        if progress_callback and idx % 100 == 0:
            progress_callback(idx, len(legacy_folders))

    return result


def run_migration_async(
    base_path: Path,
    dry_run: bool = False,
    max_folders: Optional[int] = None
) -> threading.Thread:
    """
    Run migration in a background thread (for large migrations).

    Args:
        base_path: Base path (exports/json/)
        dry_run: If True, only simulate the migration
        max_folders: Maximum number of folders to process

    Returns:
        Thread object (already started)
    """
    def _worker():
        logger.info("[MIGRATION] Running migration in background thread")

        def progress_callback(current, total):
            logger.info(f"[MIGRATION] Progress: {current}/{total}")

        result = run_migration(base_path, dry_run, max_folders, progress_callback)

        # Log summary
        logger.info("[MIGRATION] ========== SUMMARY ==========")
        logger.info(f"[MIGRATION] Total found: {result.total_found}")
        logger.info(f"[MIGRATION] Migrated: {result.migrated}")
        logger.info(f"[MIGRATION] Already migrated: {result.already_migrated}")
        logger.info(f"[MIGRATION] Skipped: {result.skipped}")
        logger.info(f"[MIGRATION] Errors: {result.errors}")

        if result.errors > 0:
            logger.error("[MIGRATION] Errors occurred during migration:")
            for folder_name, error_msg in result.error_details[:10]:  # Show first 10 errors
                logger.error(f"[MIGRATION]   - {folder_name}: {error_msg}")
            if len(result.error_details) > 10:
                logger.error(f"[MIGRATION]   ... and {len(result.error_details) - 10} more errors")

        logger.info("[MIGRATION] ==============================")

    thread = threading.Thread(target=_worker, daemon=True, name="LegacyMigration")
    thread.start()
    return thread
