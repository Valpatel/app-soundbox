"""Exercise the actual queue route without importing GPU dependencies."""
import ast
from pathlib import Path
import threading
from flask import Flask, jsonify


def test_public_queue_details_and_private_redaction():
    app = Flask(__name__)
    jobs = {
        'public': dict(status='processing', prompt='Layered ambient piano', model='music',
                       duration=90, loop=True, radio_station='piano', is_public=True,
                       user_id='must-not-leak', progress_pct=25, priority='free'),
        'private': dict(status='queued', prompt='Private text', radio_station='private-name',
                        is_public=False, user_id='must-not-leak'),
        'legacy': dict(status='queued', prompt='Unknown visibility'),
        'finished': dict(status='completed', prompt='Not queued', is_public=True),
    }
    source = Path(__file__).resolve().parents[1] / 'app.py'
    node = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'api_queue')
    ns = dict(app=app, jsonify=jsonify, jobs=jobs, queue_lock=threading.Lock(),
              current_job='public', PRIORITY_LEVELS={'free': 2})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), ns)
    response = app.test_client().get('/api/queue')
    assert response.status_code == 200
    data = response.json
    assert data['total'] == 3
    items = {j['id']: j for j in data['jobs']}
    assert items['public']['prompt'] == 'Layered ambient piano'
    assert items['public']['radio_station'] == 'piano'
    assert items['public']['loop'] is True
    assert items['public']['duration'] == 90
    assert items['public']['progress_pct'] == 25
    for key in ('private', 'legacy'):
        assert items[key]['prompt'] == 'Private generation'
        assert items[key]['radio_station'] is None
    assert 'must-not-leak' not in response.text
    assert 'Private text' not in response.text
