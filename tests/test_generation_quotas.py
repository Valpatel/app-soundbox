"""Exercise the real admission handler and Flask limiter without loading GPU models.
Run: python -m unittest discover -s tests -p test_generation_quotas.py
"""
import ast
from datetime import datetime
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import uuid
from flask import Flask, jsonify, request
from flask_limiter import Limiter


class GenerationQuotasTest(unittest.TestCase):
    def build(self, setting=None):
        app = Flask(__name__)
        limiter = Limiter(lambda: 'test-client', app=app, storage_uri='memory://')
        namespace = dict(os=os, app=app, limiter=limiter, request=request, jsonify=jsonify,
                         threading=threading, uuid=uuid, datetime=datetime,
                         require_auth_or_localhost=lambda fn: fn,
                         validate_prompt=lambda value, **kw: (True, value, None),
                         OPEN_ACCESS_MODE=True, is_localhost_request=lambda: False,
                         jobs={}, queue_lock=threading.Lock(), loading_status={'music': 'ready'})
        names = {'MAX_QUEUE_SIZE', 'GENERATION_QUOTAS_ENABLED', 'MAX_PENDING_PER_USER',
                 'GENERATION_LIMITS', 'PRIORITY_LEVELS', 'get_user_tier',
                 'count_user_pending_jobs', 'validate_integer', 'require_json_content_type', 'generate', 'api_tts_generate'}
        source = Path(__file__).resolve().parents[1] / 'app.py'
        nodes = []
        for node in ast.parse(source.read_text()).body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                nodes.append(node)
        with patch.dict(os.environ, {}, clear=False):
            if setting is None:
                os.environ.pop('SOUNDBOX_GENERATION_QUOTAS', None)
            else:
                os.environ['SOUNDBOX_GENERATION_QUOTAS'] = setting
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        @app.before_request
        def identity():
            request.user_id = 'test-user'
            request.user = {'tier': 'free'}
        return app.test_client(), namespace

    def test_default_retains_hourly_limit(self):
        client, _ = self.build()
        for _ in range(60):
            self.assertEqual(client.post('/generate', json={'model': 'invalid'}).status_code, 400)
        self.assertEqual(client.post('/generate', json={'model': 'invalid'}).status_code, 429)

    def test_private_mode_has_no_hourly_quota(self):
        client, _ = self.build('false')
        for _ in range(65):
            self.assertEqual(client.post('/generate', json={'model': 'invalid'}).status_code, 400)

    def test_pending_quota_optional_but_global_capacity_stays(self):
        for setting, expected in ((None, 429), ('false', 200)):
            client, ns = self.build(setting)
            ns['jobs'].update({str(i): {'user_id': 'test-user', 'status': 'queued'} for i in range(3)})
            response = client.post('/generate', json={'model': 'music', 'duration': 120})
            self.assertEqual(response.status_code, expected)
            if setting:
                self.assertIsNone(response.json['limits']['per_hour'])
                ns['jobs'].update({str(i): {'user_id': 'someone-else', 'status': 'queued'} for i in range(100)})
                self.assertEqual(client.post('/generate', json={'model': 'music'}).status_code, 503)

    def test_speech_quota_is_optional(self):
        for setting, expected in ((None, 429), ('false', 400)):
            client, _ = self.build(setting)
            for _ in range(60):
                self.assertEqual(client.post('/api/tts/generate', json={'text': ''}).status_code, 400)
            self.assertEqual(client.post('/api/tts/generate', json={'text': ''}).status_code, expected)

    def test_private_mode_preserves_duration_validation(self):
        client, _ = self.build('false')
        self.assertEqual(client.post('/generate', json={'duration': 181}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
