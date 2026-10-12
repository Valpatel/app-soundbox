#!/usr/bin/env python3
"""Apply reviewed source diffs to the installed image, preserving its other customizations.
Run on the Docker host with --patch for each reviewed diff. Refuses busy queues.
Creates an immutable derived image and persistent Compose override; never removes volumes.
"""
import argparse
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
    a = p.parse_args()
    container = 'app-soundbox-soundbox-1'
    info = json.loads(run(['docker', 'inspect', container]))[0]
    root = Path(info['Config']['Labels']['com.docker.compose.project.working_dir'])
    override = root / 'docker-compose.override.yml'
    if override.exists():
        raise SystemExit('Existing Compose override: reconcile it explicitly; refusing overwrite')
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
        for name in ('app.py', 'database.py'):
            compile((stage / name).read_text(), name, 'exec')
        image = 'soundbox-reviewed:' + str(time.time_ns())
        base = 'soundbox-base:' + info['Image'].split(':')[-1][:16]
        run(['docker', 'tag', info['Image'], base])
        (stage / 'Dockerfile').write_text('FROM ' + base + '\nCOPY app.py database.py /app/\nCOPY templates/index.html /app/templates/index.html\nENV PYTHONUNBUFFERED=1\n')
        if not a.apply:
            print('Patches and Python syntax verified; no deployment')
            return
        subprocess.run(['docker', 'build', '-t', image, str(stage)], check=True)
        with urllib.request.urlopen('http://127.0.0.1:5309/status', timeout=5) as response:
            if json.load(response).get('queue_length') != 0:
                raise SystemExit('Queue became busy; image built but not deployed')
        override.write_text(json.dumps({'services': {'soundbox': {'image': image}}}, indent=2) + '\n')
        receipt = root / ('soundbox-release-' + str(time.time_ns()) + '.json')
        receipt.write_text(json.dumps({'old_image': info['Image'], 'new_image': image, 'override': str(override)}, indent=2))
        print('Rollback receipt:', receipt)
        subprocess.run(['docker', 'compose', 'up', '-d', '--no-build', 'soundbox'], cwd=root, check=True)


if __name__ == '__main__':
    main()
