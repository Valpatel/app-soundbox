#!/usr/bin/env python3
"""Apply reviewed source diffs to the installed image, preserving its other customizations.
Run on the Docker host with --patch for each reviewed diff. Refuses busy queues.
Creates an immutable derived image and persistent Compose override; never removes volumes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--patch', action='append', required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--source-revision', action='append', default=[], help='Contributing Git revision for visible build metadata')
    p.add_argument('--generation-quotas', choices=('true', 'false'), help='Explicit generation quota setting for the derived image')
    p.add_argument('--expected-image', help='Explicitly replace a prior image-only override with this exact image tag')
    a = p.parse_args()
    container = 'app-soundbox-soundbox-1'
    info = json.loads(run(['docker', 'inspect', container]))[0]
    root = Path(info['Config']['Labels']['com.docker.compose.project.working_dir'])
    override = root / 'docker-compose.override.yml'
    previous_override = override.read_text() if override.exists() else None
    if previous_override is not None:
        expected = {'services': {'soundbox': {'image': a.expected_image}}}
        try:
            matches = a.expected_image and json.loads(previous_override) == expected
        except ValueError:
            matches = False
        if not matches or info['Config']['Image'] != a.expected_image:
            raise SystemExit('Override is not the explicitly expected installed image-only configuration; refusing overwrite')
    with urllib.request.urlopen('http://127.0.0.1:5309/status', timeout=5) as response:
        if json.load(response).get('queue_length') != 0:
            raise SystemExit('Queue is busy; leave running jobs intact')
    with tempfile.TemporaryDirectory(prefix='soundbox-release-') as temp:
        stage = Path(temp)
        for name in ('app.py', 'database.py', 'templates/index.html'):
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            run(['docker', 'cp', container + ':/app/' + name, str(target)])
        for patch in a.patch:
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(Path(patch).resolve())], cwd=stage, check=True)
        for source in stage.glob('*.py'):
            compile(source.read_text(), source.name, 'exec')
        image = 'soundbox-reviewed:' + str(time.time_ns())
        base = 'soundbox-base:' + info['Image'].split(':')[-1][:16]
        run(['docker', 'tag', info['Image'], base])
        digest = hashlib.sha256()
        for name in sorted([p.name for p in stage.glob('*.py')] + ['templates/index.html']):
            digest.update(name.encode() + b'\0' + (stage / name).read_bytes())
        (stage / 'build-info.json').write_text(json.dumps({
            'build_id': digest.hexdigest(), 'built_at': datetime.now(timezone.utc).isoformat(),
            'source_revisions': a.source_revision, 'base_image': info['Image']}))
        quota_env = '' if a.generation_quotas is None else 'ENV SOUNDBOX_GENERATION_QUOTAS=' + a.generation_quotas + '\n'
        (stage / 'Dockerfile').write_text('FROM ' + base + '\nCOPY *.py /app/\nCOPY templates/index.html /app/templates/index.html\nCOPY build-info.json /app/static/build-info.json\nENV PYTHONUNBUFFERED=1\n' + quota_env)
        if not a.apply:
            print('Patches and Python syntax verified; no deployment')
            return
        subprocess.run(['docker', 'build', '-t', image, str(stage)], check=True)
        with urllib.request.urlopen('http://127.0.0.1:5309/status', timeout=5) as response:
            if json.load(response).get('queue_length') != 0:
                raise SystemExit('Queue became busy; image built but not deployed')
        if (override.read_text() if override.exists() else None) != previous_override:
            raise SystemExit('Compose override changed during build; refusing deployment')
        current = json.loads(run(['docker', 'inspect', container]))[0]
        if current['Id'] != info['Id'] or current['Image'] != info['Image']:
            raise SystemExit('Container changed during build; refusing deployment')
        override.write_text(json.dumps({'services': {'soundbox': {'image': image}}}, indent=2) + '\n')
        receipt = root / ('soundbox-release-' + str(time.time_ns()) + '.json')
        receipt.write_text(json.dumps({'old_image': info['Image'], 'new_image': image, 'override': str(override), 'previous_override': previous_override}, indent=2))
        print('Rollback receipt:', receipt)
        subprocess.run(['docker', 'compose', 'up', '-d', '--no-build', 'soundbox'], cwd=root, check=True)


if __name__ == '__main__':
    main()
