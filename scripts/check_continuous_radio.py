#!/usr/bin/env python3
"""Play past the end of All Music repeatedly while a new song is pending (no GPU)."""
import argparse
import io
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--html')
args = parser.parse_args()
tracks = [dict(id=c * 32, filename=c + '.wav', prompt='Radio music ' + c, model='music',
               duration=90, upvotes=0, downvotes=0) for c in ('a', 'b')]
buf = io.BytesIO()
with wave.open(buf, 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
    wav.writeframes(b'\0\0' * 8000 * 90)
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                args=['--autoplay-policy=no-user-gesture-required'])
    for width in (390, 1440):
        page = browser.new_page(bypass_csp=True, viewport={'width': width, 'height': 1000})
        fills = []
        if args.html:
            page.route(args.url.rstrip('/') + '/', lambda r: r.fulfill(content_type='text/html', body=Path(args.html).read_text()))
        page.route('**/api/radio/shuffle?*', lambda r: r.fulfill(json={'tracks': tracks}))
        page.route('**/api/radio/next?*', lambda r: r.fulfill(json={'tracks': []}))
        def fill(r):
            fills.append(r.request.post_data_json)
            r.fulfill(status=202, json={'job_id': 'c' * 32})
        page.route('**/api/radio/fill', fill)
        page.route('**/job/' + 'c' * 32, lambda r: r.fulfill(json={'status': 'processing', 'progress': 'Generating music... 20%'}))
        page.route('**/audio/*.wav', lambda r: r.fulfill(content_type='audio/wav', body=buf.getvalue()))
        page.goto(args.url, wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
        page.locator('.station-all').click()
        page.wait_for_function('currentRadioTrack !== null && !radioPlayer.paused')
        page.wait_for_function('radioFillSession === radioSession')
        assert len(fills) == 1, 'Prefetch starts before current songs end'
        seen = []
        for _ in range(6):
            seen.append(page.evaluate('currentRadioTrack.id'))
            expect(page.locator('#now-playing')).to_be_visible()
            expect(page.locator('#radio-queue')).to_be_visible()
            assert page.evaluate('!radioPlayer.paused')
            page.evaluate("radioPlayer.dispatchEvent(new Event('ended'))")
            page.wait_for_function('currentRadioTrack !== null && !radioPlayer.paused')
        assert seen == [tracks[i % 2]['id'] for i in range(6)], seen
        assert len(fills) == 1, 'Repeated playback must share the pending generation'
        page.get_by_role('button', name='Stop radio', exact=True).click()
        page.wait_for_timeout(3200)
        assert page.evaluate('radioPlayer.paused && !radioUserStarted')
        expect(page.locator('#radio-queue')).to_contain_text('Nothing queued next')
        print(f'{width}px: continuous rotation, prefetch, persistent player/queue and Stop passed', flush=True)
        page.close()
    browser.close()
