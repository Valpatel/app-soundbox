#!/usr/bin/env python3
"""Snapshot or restore Soundbox using configured S3-compatible storage."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from object_storage import S3Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    snapshot = commands.add_parser('snapshot')
    snapshot.add_argument('--database', type=Path, required=True)
    snapshot.add_argument('--audio-dir', type=Path, required=True)
    snapshot.add_argument('--metadata', type=Path, help='Optional legacy generations.json to retain')
    restore = commands.add_parser('restore')
    restore.add_argument('--destination', type=Path, required=True, help='New, nonexisting directory')
    args = parser.parse_args()
    store = S3Store.from_env()
    if not store:
        parser.error('Configure SOUNDBOX_STORAGE=s3 and S3 credentials first')
    if args.command == 'snapshot':
        result = store.snapshot(args.database, args.audio_dir, args.metadata)
    else:
        result = store.restore(args.destination)
    print(json.dumps({'snapshot_id': result['snapshot_id'], 'audio_objects': len(result['audio']),
                      'created_at': result['created_at']}))


if __name__ == '__main__':
    main()
