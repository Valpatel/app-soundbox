#!/usr/bin/env python3
"""Publish existing saved audio after making a SQLite backup. Dry run by default."""
import argparse
import json
from pathlib import Path
import sqlite3
import time


def publish(path, apply=False):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(str(path)) as connection:
        count = connection.execute('SELECT count(*) FROM generations WHERE NOT is_public OR is_public IS NULL').fetchone()[0]
        result = {'private_records': count, 'applied': False}
        if apply and count:
            backup = path.with_name(path.name + '.before-public-' + str(time.time_ns()))
            backup.touch(mode=0o600, exist_ok=False)
            with sqlite3.connect(str(backup)) as target:
                connection.backup(target)
            with connection:
                connection.execute('UPDATE generations SET is_public=1, admin_reviewed=1 WHERE NOT is_public OR is_public IS NULL')
            result.update(applied=True, backup=str(backup))
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish(args.database, args.apply)))
