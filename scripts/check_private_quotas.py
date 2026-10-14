#!/usr/bin/env python3
"""Verify private generation quota opt-out using rejected input; creates no jobs."""
import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', required=True)
args = parser.parse_args()
for endpoint, body, expected_error in (
    ('/generate', {'model': 'invalid-quota-probe', 'prompt': 'Quiet piano', 'duration': 3}, 'Invalid model type'),
    ('/api/tts/generate', {'text': ''}, 'Text is required'),
):
    for attempt in range(65):
        req = Request(args.url.rstrip('/') + endpoint, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=15) as response:
                raise AssertionError('Invalid probe unexpectedly accepted: ' + str(response.status))
        except HTTPError as exc:
            result = json.load(exc)
            assert exc.code == 400 and result.get('error') == expected_error, (endpoint, attempt, exc.code, result)
    print(json.dumps({'endpoint': endpoint, 'rejected_inputs': 65, 'quota_rejections': 0}), flush=True)
