#!/usr/bin/env python3
"""Stamp source identity without publishing local paths or environment secrets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path('.'))
parser.add_argument('--revision', action='append', default=[])
args = parser.parse_args()
fingerprint = hashlib.sha256()
for name in ('app.py', 'database.py', 'templates/index.html'):
    fingerprint.update(name.encode() + b'\0' + (args.root / name).read_bytes())
output = args.root / 'static/build-info.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({'build_id': fingerprint.hexdigest(),
    'built_at': datetime.now(timezone.utc).isoformat(), 'source_revisions': args.revision}, indent=2) + '\n')
