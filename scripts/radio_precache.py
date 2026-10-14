#!/usr/bin/env python3
"""Bounded, resumable music precache through Soundbox's normal API.

One admitted job at a time; existing interactive queues take precedence. Persist
state after every response. An ambiguous POST failure stops for operator review.
No recurring daemon: --until is required and bounds admissions, not running jobs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radio_catalog import STATIONS

CATEGORIES = ('ambient', 'retro', 'piano', 'happy', 'dreamy', 'lofi')
TEXTURES = ('warm analog synths', 'delicate bells', 'soft electric piano',
            'gentle arpeggios', 'flowing strings', 'plucked melodic accents',
            'rounded bass notes', 'layered harmonies')
MOODS = ('peaceful', 'hopeful', 'curious', 'reflective', 'playful', 'luminous')


def choose_station(tracks):
    """Fill scarce categories first; positive listening/voting signals raise targets.

    This is a bounded stocking heuristic, not a claim to predict musical quality.
    Majority-downvoted tracks do not count towards available stock.
    """
    scores = []
    for station in CATEGORIES:
        words = STATIONS[station][0].split()
        matching = [t for t in tracks if t.get('model') == 'music' and
                    any(w in t.get('prompt', '').lower() for w in words)]
        eligible = [t for t in matching if (t.get('downvotes') or 0) <= (t.get('upvotes') or 0)]
        demand = sum(max(0, (t.get('upvotes') or 0) - (t.get('downvotes') or 0)) +
                     (t.get('play_count') or 0) // 10 for t in eligible)
        target = 8 + min(16, demand)
        scores.append((len(eligible) / target, len(eligible), station))
    return min(scores)[2]


class API:
    def __init__(self, url):
        self.url = url.rstrip('/')

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    def library(self):
        tracks = []
        for page in range(1, 1001):
            result = self.call(f'/api/library?model=music&per_page=100&page={page}')
            tracks.extend(result.get('items', []))
            if page >= result.get('pages', 1):
                return tracks
        raise RuntimeError('Library exceeds scan bound; refusing partial inventory')


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.replace(path)


def step(api, state, until, max_tracks, paused=False, now=None):
    now = now or datetime.now(timezone.utc)
    if state.get('uncertain_submission'):
        raise RuntimeError('Previous submission was ambiguous; inspect server queue before clearing state')
    job_id = state.get('current_job')
    if job_id:
        job = api.call('/job/' + job_id)
        state['progress'] = job.get('progress', job.get('status'))
        if job.get('status') == 'completed':
            track = api.call('/api/library/' + job_id)
            if not track.get('filename') or not track.get('is_public'):
                raise RuntimeError('Completed job is not available in the shared library')
            state.setdefault('completed', []).append({'id': job_id, 'station': state['station'],
                                                       'filename': track['filename'], 'duration': track['duration']})
            state['current_job'] = None
            state['failures'] = 0
        elif job.get('status') in ('failed', 'error', 'cancelled', 'skipped'):
            state.setdefault('failed', []).append({'id': job_id, 'status': job['status']})
            state['current_job'] = None
            state['failures'] = state.get('failures', 0) + 1
        return 'waiting'
    if now >= until or len(state.get('completed', [])) >= max_tracks:
        return 'finished'
    if state.get('failures', 0) >= 3:
        raise RuntimeError('Three consecutive failures; batch stopped')
    if paused or api.call('/api/queue').get('total', 0):
        return 'paused'
    if api.call('/status').get('models', {}).get('music') != 'ready':
        return 'warming'
    station = choose_station(api.library())
    prompt = (STATIONS[station][1] + ', ' + random.choice(MOODS) + ' mood, ' +
              random.choice(TEXTURES) + ', instrumental without vocals, evolving arrangement')
    duration = random.choice((60, 90, 120))
    state['station'] = station
    state['uncertain_submission'] = True
    # Persist intent before submitting: a crash cannot silently duplicate this job.
    state['_persist']()
    result = api.call('/generate', {'prompt': prompt, 'model': 'music', 'duration': duration, 'loop': False})
    if not result.get('job_id'):
        raise RuntimeError('No job id returned; inspect queue before retrying')
    state['current_job'] = result['job_id']
    state['uncertain_submission'] = False
    state['progress'] = 'Submitted'
    return 'submitted'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:5309')
    parser.add_argument('--until', required=True, help='ISO timestamp including timezone')
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--pause-file', type=Path)
    parser.add_argument('--max-tracks', type=int, default=120)
    args = parser.parse_args()
    until = datetime.fromisoformat(args.until)
    if until.tzinfo is None or not 1 <= args.max_tracks <= 1000:
        parser.error('Use a timezone-aware deadline and max-tracks 1..1000')
    # Prevent two processes from admitting work with the same state file.
    import fcntl
    args.state.parent.mkdir(parents=True, exist_ok=True)
    lock = args.state.with_suffix('.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = json.loads(args.state.read_text()) if args.state.exists() else {}
    def persist():
        save(args.state, {k: v for k, v in state.items() if not k.startswith('_')})
    state['_persist'] = persist
    api = API(args.url)
    try:
        while True:
            status = step(api, state, until, args.max_tracks,
                          bool(args.pause_file and args.pause_file.exists()))
            state['status'] = status
            state['updated_at'] = datetime.now(timezone.utc).isoformat()
            persist()
            print(json.dumps({k: state.get(k) for k in ('status', 'current_job', 'station', 'progress')}) , flush=True)
            if status == 'finished':
                break
            time.sleep(20)
    finally:
        persist()


if __name__ == '__main__':
    main()
