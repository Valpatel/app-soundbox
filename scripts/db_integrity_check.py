#!/usr/bin/env python3
"""
Database Integrity Check Script

Checks for:
1. Orphaned database records (no matching audio file)
2. Audio files without database entries
3. Invalid JSON in category column
4. FTS5 index sync issues
5. Foreign key violations
6. Data consistency issues
"""

import sqlite3
import json
import os
import sys

DB_PATH = '/home/mvalancy/Code/app-soundbox/soundbox.db'
AUDIO_DIR = '/home/mvalancy/Code/app-soundbox/generated'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_orphaned_db_records():
    """Find database records with no matching audio file."""
    print("\n=== Checking for orphaned database records ===")
    conn = get_db()
    cursor = conn.execute("SELECT id, filename FROM generations")

    orphaned = []
    for row in cursor:
        filepath = os.path.join(AUDIO_DIR, row['filename'])
        if not os.path.exists(filepath):
            orphaned.append((row['id'], row['filename']))

    conn.close()

    if orphaned:
        print(f"  ISSUE: Found {len(orphaned)} orphaned records (no audio file)")
        for gen_id, filename in orphaned[:10]:
            print(f"    - {gen_id}: {filename}")
        if len(orphaned) > 10:
            print(f"    ... and {len(orphaned) - 10} more")
        return False
    else:
        print("  OK: All database records have matching audio files")
        return True


def check_orphaned_audio_files():
    """Find audio files without database entries."""
    print("\n=== Checking for orphaned audio files ===")

    if not os.path.exists(AUDIO_DIR):
        print(f"  SKIP: Audio directory not found: {AUDIO_DIR}")
        return True

    conn = get_db()
    cursor = conn.execute("SELECT filename FROM generations")
    db_files = set(row['filename'] for row in cursor)
    conn.close()

    orphaned = []
    for filename in os.listdir(AUDIO_DIR):
        if filename.endswith(('.wav', '.mp3', '.ogg', '.flac')):
            if filename not in db_files:
                orphaned.append(filename)

    if orphaned:
        print(f"  ISSUE: Found {len(orphaned)} orphaned audio files (no DB entry)")
        for filename in orphaned[:10]:
            print(f"    - {filename}")
        if len(orphaned) > 10:
            print(f"    ... and {len(orphaned) - 10} more")
        return False
    else:
        print("  OK: All audio files have database entries")
        return True


def check_invalid_json_categories():
    """Check for invalid JSON in category column."""
    print("\n=== Checking for invalid JSON in categories ===")
    conn = get_db()
    cursor = conn.execute("SELECT id, category FROM generations WHERE category IS NOT NULL")

    invalid = []
    for row in cursor:
        try:
            if row['category']:
                data = json.loads(row['category'])
                if not isinstance(data, list):
                    invalid.append((row['id'], row['category'], 'Not a list'))
        except json.JSONDecodeError as e:
            invalid.append((row['id'], row['category'][:50], str(e)))

    conn.close()

    if invalid:
        print(f"  ISSUE: Found {len(invalid)} records with invalid JSON categories")
        for gen_id, cat, err in invalid[:10]:
            print(f"    - {gen_id}: {cat} ({err})")
        return False
    else:
        print("  OK: All category JSON is valid")
        return True


def check_fts_sync():
    """Check if FTS5 index is in sync with main table."""
    print("\n=== Checking FTS5 index sync ===")
    conn = get_db()

    # Count records in main table
    main_count = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]

    # Count records in FTS table
    try:
        fts_count = conn.execute("SELECT COUNT(*) FROM generations_fts").fetchone()[0]
    except sqlite3.OperationalError:
        print("  SKIP: FTS table not found")
        conn.close()
        return True

    conn.close()

    if main_count != fts_count:
        print(f"  ISSUE: FTS index out of sync (main: {main_count}, fts: {fts_count})")
        print("  FIX: Run 'INSERT INTO generations_fts(generations_fts) VALUES(\"rebuild\")' to rebuild")
        return False
    else:
        print(f"  OK: FTS index in sync ({main_count} records)")
        return True


def check_foreign_keys():
    """Check for foreign key violations."""
    print("\n=== Checking foreign key integrity ===")
    conn = get_db()

    # Enable foreign key checks
    conn.execute("PRAGMA foreign_keys = ON")

    violations = []

    # Check votes -> generations
    cursor = conn.execute("""
        SELECT v.id, v.generation_id FROM votes v
        LEFT JOIN generations g ON v.generation_id = g.id
        WHERE g.id IS NULL
    """)
    for row in cursor:
        violations.append(('votes', row['id'], row['generation_id']))

    # Check favorites -> generations
    cursor = conn.execute("""
        SELECT f.id, f.generation_id FROM favorites f
        LEFT JOIN generations g ON f.generation_id = g.id
        WHERE g.id IS NULL
    """)
    for row in cursor:
        violations.append(('favorites', row['id'], row['generation_id']))

    # Check playlist_tracks -> generations
    cursor = conn.execute("""
        SELECT pt.id, pt.generation_id FROM playlist_tracks pt
        LEFT JOIN generations g ON pt.generation_id = g.id
        WHERE g.id IS NULL
    """)
    for row in cursor:
        violations.append(('playlist_tracks', row['id'], row['generation_id']))

    # Check play_events -> generations
    cursor = conn.execute("""
        SELECT pe.id, pe.generation_id FROM play_events pe
        LEFT JOIN generations g ON pe.generation_id = g.id
        WHERE g.id IS NULL
    """)
    for row in cursor:
        violations.append(('play_events', row['id'], row['generation_id']))

    conn.close()

    if violations:
        print(f"  ISSUE: Found {len(violations)} foreign key violations")
        for table, row_id, gen_id in violations[:10]:
            print(f"    - {table}.{row_id} references missing generation {gen_id}")
        return False
    else:
        print("  OK: No foreign key violations")
        return True


def check_duplicate_filenames():
    """Check for duplicate filenames."""
    print("\n=== Checking for duplicate filenames ===")
    conn = get_db()

    cursor = conn.execute("""
        SELECT filename, COUNT(*) as cnt FROM generations
        GROUP BY filename HAVING cnt > 1
    """)

    duplicates = list(cursor)
    conn.close()

    if duplicates:
        print(f"  ISSUE: Found {len(duplicates)} duplicate filenames")
        for row in duplicates[:10]:
            print(f"    - {row['filename']}: {row['cnt']} copies")
        return False
    else:
        print("  OK: No duplicate filenames")
        return True


def check_null_required_fields():
    """Check for NULL values in required fields."""
    print("\n=== Checking for NULL required fields ===")
    conn = get_db()

    issues = []

    # Check for NULL prompts
    count = conn.execute("SELECT COUNT(*) FROM generations WHERE prompt IS NULL OR prompt = ''").fetchone()[0]
    if count > 0:
        issues.append(f"  - {count} records with NULL/empty prompt")

    # Check for NULL filenames
    count = conn.execute("SELECT COUNT(*) FROM generations WHERE filename IS NULL OR filename = ''").fetchone()[0]
    if count > 0:
        issues.append(f"  - {count} records with NULL/empty filename")

    # Check for NULL models
    count = conn.execute("SELECT COUNT(*) FROM generations WHERE model IS NULL OR model = ''").fetchone()[0]
    if count > 0:
        issues.append(f"  - {count} records with NULL/empty model")

    # Check for invalid durations
    count = conn.execute("SELECT COUNT(*) FROM generations WHERE duration IS NULL OR duration <= 0").fetchone()[0]
    if count > 0:
        issues.append(f"  - {count} records with invalid duration")

    conn.close()

    if issues:
        print("  ISSUES found:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("  OK: All required fields have valid values")
        return True


def check_model_values():
    """Check that model values are valid."""
    print("\n=== Checking model values ===")
    conn = get_db()

    cursor = conn.execute("SELECT DISTINCT model FROM generations")
    models = [row['model'] for row in cursor]
    conn.close()

    valid_models = {'music', 'audio', 'voice'}
    invalid = [m for m in models if m not in valid_models]

    if invalid:
        print(f"  WARNING: Found non-standard model values: {invalid}")
        print(f"  Valid models: {valid_models}")
        return False
    else:
        print(f"  OK: All model values are valid: {models}")
        return True


def get_stats():
    """Get database statistics."""
    print("\n=== Database Statistics ===")
    conn = get_db()

    # Total generations
    total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    print(f"  Total generations: {total}")

    # By model
    cursor = conn.execute("SELECT model, COUNT(*) as cnt FROM generations GROUP BY model ORDER BY cnt DESC")
    print("  By model:")
    for row in cursor:
        print(f"    - {row['model']}: {row['cnt']}")

    # Total votes
    votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    print(f"  Total votes: {votes}")

    # Total favorites
    favorites = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    print(f"  Total favorites: {favorites}")

    # Total play events
    plays = conn.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]
    print(f"  Total play events: {plays}")

    conn.close()


def cleanup_orphaned_db_records(dry_run=True):
    """Remove database records with no matching audio file."""
    print("\n=== Cleaning up orphaned database records ===")
    conn = get_db()
    cursor = conn.execute("SELECT id, filename FROM generations")

    orphaned = []
    for row in cursor:
        filepath = os.path.join(AUDIO_DIR, row['filename'])
        if not os.path.exists(filepath):
            orphaned.append(row['id'])

    if not orphaned:
        print("  No orphaned records to clean up")
        conn.close()
        return 0

    if dry_run:
        print(f"  Would delete {len(orphaned)} orphaned records (use --fix to apply)")
    else:
        # Delete orphaned records
        placeholders = ','.join('?' * len(orphaned))
        conn.execute(f"DELETE FROM generations WHERE id IN ({placeholders})", orphaned)
        conn.commit()
        print(f"  Deleted {len(orphaned)} orphaned records")

    conn.close()
    return len(orphaned)


def rebuild_fts_index():
    """Rebuild FTS5 index."""
    print("\n=== Rebuilding FTS5 index ===")
    conn = get_db()
    try:
        conn.execute("INSERT INTO generations_fts(generations_fts) VALUES('rebuild')")
        conn.commit()
        print("  FTS index rebuilt successfully")
    except sqlite3.OperationalError as e:
        print(f"  Error rebuilding FTS: {e}")
    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Database integrity check and cleanup')
    parser.add_argument('--fix', action='store_true', help='Fix issues (delete orphaned records)')
    parser.add_argument('--rebuild-fts', action='store_true', help='Rebuild FTS5 index')
    args = parser.parse_args()

    print("=" * 60)
    print("DATABASE INTEGRITY CHECK")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    all_ok = True

    # Run all checks
    all_ok &= check_orphaned_db_records()
    all_ok &= check_orphaned_audio_files()
    all_ok &= check_invalid_json_categories()
    all_ok &= check_fts_sync()
    all_ok &= check_foreign_keys()
    all_ok &= check_duplicate_filenames()
    all_ok &= check_null_required_fields()
    all_ok &= check_model_values()

    # Apply fixes if requested
    if args.fix:
        cleanup_orphaned_db_records(dry_run=False)

    if args.rebuild_fts:
        rebuild_fts_index()

    # Show stats
    get_stats()

    print("\n" + "=" * 60)
    if all_ok:
        print("RESULT: All integrity checks passed!")
    else:
        print("RESULT: Some issues found - see above for details")
        if not args.fix:
            print("TIP: Run with --fix to clean up orphaned DB records")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
