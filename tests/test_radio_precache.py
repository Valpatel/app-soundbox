import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('precache', Path(__file__).resolve().parents[1] / 'scripts/radio_precache.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class API:
    def __init__(self):
        self.calls = []
        self.total = 0
        self.job_status = 'processing'
    def library(self):
        return []
    def call(self, path, body=None):
        self.calls.append((path, body))
        if path == '/api/queue': return {'total': self.total}
        if path == '/status': return {'models': {'music': 'ready'}}
        if path == '/generate': return {'job_id': 'abc'}
        if path == '/job/abc': return {'status': self.job_status}
        if path == '/api/library/abc': return {'filename': 'abc.wav', 'duration': 90, 'is_public': 1}
        raise AssertionError(path)

def test_one_job_at_a_time_and_stop_deadline():
    api = API()
    state = {'_persist': lambda: None}
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=1)
    assert module.step(api, state, until, 5, now=now) == 'submitted'
    for _ in range(3):
        module.step(api, state, until, 5, now=now)
    assert sum(path == '/generate' for path, _ in api.calls) == 1
    api.job_status = 'completed'
    module.step(api, state, until, 5, now=until)
    assert len(state['completed']) == 1
    assert module.step(api, state, until, 5, now=until) == 'finished'

def test_pause_busy_queue_limit_and_uncertain_submission():
    api = API()
    state = {'_persist': lambda: None}
    until = datetime.now(timezone.utc) + timedelta(hours=1)
    assert module.step(api, state, until, 5, paused=True) == 'paused'
    api.total = 1
    assert module.step(api, state, until, 5) == 'paused'
    state['completed'] = [{}]
    assert module.step(api, state, until, 1) == 'finished'
    state['uncertain_submission'] = True
    with pytest.raises(RuntimeError, match='ambiguous'):
        module.step(api, state, until, 5)
    assert not any(path == '/generate' for path, _ in api.calls)

def test_feedback_and_rejected_tracks_affect_stocking():
    tracks = [dict(model='music', prompt=module.STATIONS[s][1], upvotes=0, downvotes=0, play_count=0)
              for s in module.CATEGORIES]
    tracks[2]['upvotes'] = 10
    assert module.choose_station(tracks) == 'piano'
    tracks[0]['downvotes'] = 1
    assert module.choose_station(tracks) == 'ambient'
