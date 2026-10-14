#!/usr/bin/env python3
"""Browser regression: immediate dislikes, optional feedback, correct track identity.
Mocks audio/vote APIs; never changes real ratings or starts generation.
"""
import argparse
import io
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--url', required=True)
p.add_argument('--html')
p.add_argument('--static-dir', help='Preview modified widget JS from this directory')
p.add_argument('--modes', nargs='+', default=['radio', 'dismiss', 'mini', 'library', 'nonplaying', 'failure', 'undo'])
a = p.parse_args()
tracks = [dict(id=c * 32, filename=c + '.wav', prompt='Track ' + c.upper(), model='music',
               duration=90, upvotes=0, downvotes=0) for c in 'abc']
audio = io.BytesIO()
with wave.open(audio, 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
    wav.writeframes(b'\0\0' * 8000 * 90)

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                args=['--autoplay-policy=no-user-gesture-required'])
    for width in (390, 1440):
        for mode in a.modes:
            page = browser.new_page(bypass_csp=True, viewport={'width': width, 'height': 1000})
            held, requests, errors = [], [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            if a.html:
                page.route(a.url.rstrip('/') + '/', lambda r: r.fulfill(content_type='text/html', body=Path(a.html).read_text()))
            if a.static_dir:
                page.route('**/static/js/radio-widget*.js', lambda r: r.fulfill(content_type='text/javascript', body=(Path(a.static_dir) / r.request.url.split('/')[-1].split('?')[0]).read_text()))
            page.route('**/audio/*.wav', lambda r: r.fulfill(content_type='audio/wav', body=audio.getvalue()))
            page.route('**/api/radio/**', lambda r: r.fulfill(json={'tracks': []}))
            page.route('**/api/library?*', lambda r: r.fulfill(json={'items': tracks, 'total': 3, 'pages': 1, 'page': 1}))
            page.route('**/api/library/votes', lambda r: r.fulfill(json={'votes': {}}))
            def vote(r):
                requests.append((r.request.url, r.request.post_data_json))
                held.append(r)
            page.route('**/api/library/*/vote', vote)
            page.goto(a.url, wait_until='networkidle')
            page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
            page.evaluate("tracks => {switchTab('radio'); currentStation='playlist'; radioUserStarted=true; radioQueue=tracks; playNextTrack();}", tracks)
            page.wait_for_function('!radioPlayer.paused')
            if mode == 'undo':
                page.evaluate("switchTab('library')")
                page.locator('.library-item').first.wait_for()
                page.wait_for_load_state('networkidle')  # Navigation refresh must finish before playing its cards.
                page.evaluate("id => {userVotes[id]=-1; rejectedTrackIds.add(id); playNextTrack();}", tracks[0]['id'])
                page.wait_for_function('!radioPlayer.paused')
                page.locator('.library-item .vote-down').first.click()
                page.wait_for_timeout(150)
                assert len(held) == 1 and requests[0][1]['vote'] == 0
                assert requests[0][0].endswith('/' + tracks[0]['id'] + '/vote')
                held.pop().fulfill(json={'user_vote': 0, 'upvotes': 0, 'downvotes': 0})
                page.wait_for_timeout(150)
                assert page.evaluate('id => !rejectedTrackIds.has(id)', tracks[0]['id'])
                assert page.evaluate('currentRadioTrack.id') == tracks[1]['id']
                assert page.evaluate('!radioPlayer.paused')
                assert not errors, errors
                print(f'{width}px undo: real vote endpoint, restored eligibility and no unrelated skip passed', flush=True)
                page.close()
                continue
            if mode in ('mini', 'library', 'nonplaying'):
                page.evaluate("switchTab('library')")
                page.locator('.library-item').first.wait_for()
                page.wait_for_load_state('networkidle')  # Navigation refresh must finish before playing its cards.
                if mode == 'library':
                    page.locator('.library-item audio').first.evaluate('a => a.play()')
                else:
                    page.locator('#mini-player-play').click()
            if mode == 'mini':
                page.locator('#mini-vote-down').click()
            elif mode in ('library', 'nonplaying'):
                index = 0 if mode == 'library' else 2
                page.locator('.library-item .vote-down').nth(index).click()
            else:
                page.locator('#radio-vote-down').click()
            page.wait_for_timeout(150)
            assert len(held) == 1, requests
            expected_id = tracks[2 if mode == 'nonplaying' else 0]['id']
            assert requests[0][0].endswith('/' + expected_id + '/vote')
            assert requests[0][1]['vote'] == -1
            if mode == 'library':
                assert page.locator('.library-item audio').first.evaluate('a => a.paused')
                assert page.locator('.library-item audio').nth(1).evaluate('a => !a.paused')
            else:
                expected_current = tracks[0 if mode == 'nonplaying' else 1]['id']
                assert page.evaluate('currentRadioTrack.id') == expected_current
                assert page.evaluate('!radioPlayer.paused')
            if mode != 'mini':
                expect(page.locator('#feedback-modal-overlay')).to_be_visible()
                assert page.evaluate('feedbackModalState.track.id') == expected_id
            if mode == 'dismiss':
                page.locator('.feedback-modal-close').click()
            if mode == 'radio':
                page.locator('#feedback-modal-options .feedback-tag').first.click()
                page.locator('#feedback-modal-submit').click()
                page.wait_for_timeout(150)
                assert len(requests) == 1, 'Details must wait for the initial vote to avoid overwriting them'

            held.pop(0).fulfill(status=503 if mode == 'failure' else 200,
                               json={'error': 'Test outage'} if mode == 'failure' else
                               {'user_vote': -1, 'upvotes': 0, 'downvotes': 99})
            page.wait_for_timeout(200)
            if mode == 'radio':
                assert page.locator('#radio-downvotes').inner_text() == '0', 'Late vote must not mark next track'
                page.wait_for_timeout(150)
                assert len(held) == 1 and requests[1][0] == requests[0][0]
                assert requests[1][1]['feedback_reasons']
                held.pop().fulfill(json={'user_vote': -1, 'upvotes': 0, 'downvotes': 99})
                expect(page.locator('#feedback-modal-overlay')).to_be_hidden()
                assert page.evaluate('currentRadioTrack.id') == tracks[1]['id'], 'Feedback must not skip twice'
            elif mode == 'dismiss':
                assert len(requests) == 1, 'Closing optional feedback retains the initial vote'
            elif mode == 'failure':
                assert 'Vote was not saved' in page.locator('body').inner_text()
                assert page.evaluate('currentRadioTrack.id') == tracks[1]['id']
            assert not errors, errors
            print(f'{width}px {mode}: immediate skip, pinned vote and optional feedback passed', flush=True)
            page.close()
    browser.close()
