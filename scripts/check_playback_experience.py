#!/usr/bin/env python3
"""Check exclusive playback, radio continuity and responsive controls without GPU work."""
import argparse
import io
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--html')
args = parser.parse_args()
track = dict(id='b' * 32, filename='interlude.wav', prompt='Existing library music ' * 8,
             model='music', duration=90, upvotes=2, downvotes=1)
new_track = dict(track, id='c' * 32, filename='new-song.wav', prompt='New station music')
buffer = io.BytesIO()
with wave.open(buffer, 'wb') as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(8000)
    audio.writeframes(b'\0\0' * 8000 * 90)
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                args=['--autoplay-policy=no-user-gesture-required'])
    for width in (320, 390, 768, 1024, 1440, 1920):
        page = browser.new_page(bypass_csp=True, viewport={'width': width, 'height': 900})
        errors, fills = [], []
        state = {'complete': False}
        page.on('pageerror', lambda error: errors.append(str(error)))
        if args.html:
            page.route(args.url.rstrip('/') + '/', lambda r: r.fulfill(
                content_type='text/html', body=Path(args.html).read_text()))
        # Only unfiltered shuffle supplies interlude music. Station itself is empty.
        page.route('**/api/radio/shuffle?*', lambda r: r.fulfill(json={
            'tracks': [] if 'search=' in r.request.url else [track]}))
        page.route('**/api/radio/next?*', lambda r: r.fulfill(json={'tracks': []}))
        def fill(route):
            fills.append(route.request.post_data_json)
            route.fulfill(status=202, json={'job_id': new_track['id']})
        page.route('**/api/radio/fill', fill)
        page.route('**/job/' + new_track['id'], lambda r: r.fulfill(json={
            'status': 'completed' if state['complete'] else 'processing',
            'progress': 'Generating music... 1%'}))
        page.route('**/api/library/' + new_track['id'], lambda r: r.fulfill(json=new_track))
        page.route('**/audio/*.wav', lambda r: r.fulfill(content_type='audio/wav', body=buffer.getvalue()))
        page.route('**/api/tts/sample/*', lambda r: r.fulfill(content_type='audio/wav', body=buffer.getvalue()))
        page.goto(args.url, wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
        page.wait_for_timeout(400)
        page.locator('.station-ambient').click()
        page.wait_for_function("currentRadioTrack?.id === '" + track['id'] + "' && !radioPlayer.paused")
        expect(page.locator('#now-playing')).to_be_visible()
        expect(page.locator('#now-playing #radio-generation-status')).to_be_visible()
        assert page.locator('#now-playing .control-bar').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
        page.locator('#now-playing').scroll_into_view_if_needed()
        page.screenshot(path=f'/tmp/soundbox-radio-waiting-{width}.png')
        # Repeat interlude at exhaustion without admitting another job.
        page.evaluate("radioQueue=[]; radioPlayer.dispatchEvent(new Event('ended'))")
        page.wait_for_function('currentRadioTrack !== null && !radioPlayer.paused')
        assert len(fills) == 1
        state['complete'] = True
        page.wait_for_function("radioQueue.some(t => t.id === '" + new_track['id'] + "')", timeout=12000)
        assert page.evaluate('currentRadioTrack.id') == track['id'], 'Do not interrupt current song'
        page.evaluate("radioPlayer.dispatchEvent(new Event('ended'))")
        page.wait_for_function("currentRadioTrack?.id === '" + new_track['id'] + "'")
        page.evaluate("switchTab('library')")
        assert page.evaluate('radioPlayer.paused'), 'Tab navigation pauses radio/library transport'
        expect(page.locator('#mini-player')).to_be_visible()
        for expanded in (False, True):
            if expanded:
                page.locator('#mini-expand-btn').click()
            bounds = page.locator('#mini-player').bounding_box()
            assert bounds['x'] >= -1 and bounds['x'] + bounds['width'] <= width + 1, (width, bounds)
            for button in page.locator('#mini-player button').all():
                box = button.bounding_box()
                assert box and box['width'] >= 44 and box['height'] >= 44
                assert box['x'] >= bounds['x'] and box['x'] + box['width'] <= bounds['x'] + bounds['width'] + 1
                assert box['y'] >= bounds['y'] and box['y'] + box['height'] <= bounds['y'] + bounds['height'] + 1
        page.locator('#mini-player-play').click()
        page.wait_for_function('!radioPlayer.paused')
        # Opening Radio from its floating transport is navigation, not Stop.
        page.evaluate("window.radioNavigationBefore = {src:radioPlayer.src, time:radioPlayer.currentTime, session:radioSession, queue:JSON.stringify(radioQueue)}; window.radioPauseEvents=0; radioPlayer.addEventListener('pause', () => radioPauseEvents++)")
        page.locator('#mini-player button[title="Open Radio"]').click()
        page.wait_for_timeout(300)
        assert page.evaluate("currentTab === 'radio' && !radioPlayer.paused && radioPauseEvents === 0 && radioPlayer.src === radioNavigationBefore.src && radioPlayer.currentTime >= radioNavigationBefore.time && radioSession === radioNavigationBefore.session && JSON.stringify(radioQueue) === radioNavigationBefore.queue"), 'Radio shortcut must preserve transport, time, queue and session'
        expect(page.locator('#mini-player')).to_be_hidden()
        expect(page.locator('#now-playing')).to_be_visible()
        page.evaluate("switchTab('library')")
        page.locator('#mini-player-play').click()
        page.wait_for_function('!radioPlayer.paused')
        page.evaluate("playSample('test-voice')")
        page.wait_for_function('sampleAudio && !sampleAudio.paused')
        assert page.evaluate('radioPlayer.paused'), 'Voice preview must pause radio'
        page.evaluate("switchTab('generate')")
        assert page.evaluate('sampleAudio.paused'), 'Detached sample must pause on navigation'
        page.evaluate("document.getElementById('audio').src='/audio/interlude.wav'; document.getElementById('audio').play()")
        page.evaluate("switchTab('radio')")
        assert page.evaluate("document.getElementById('audio').paused")
        # Library card audio is a separate source from the radio transport.
        page.evaluate("switchTab('library')")
        page.wait_for_timeout(600)  # Let the navigation's library refresh settle.
        library_audio = page.locator('#library-items audio').first
        library_audio.wait_for(state='attached')
        library_audio.evaluate("el => { el.src='/audio/interlude.wav'; return el.play(); }")
        assert library_audio.evaluate('el => !el.paused')
        page.evaluate("switchTab('radio')")
        assert library_audio.evaluate('el => el.paused'), 'Library audio must stop when opening radio'
        page.evaluate("switchTab('library')")
        page.wait_for_timeout(600)
        page.locator('#library-items audio').first.evaluate("el => { window.removedAudio = el; el.src='/audio/interlude.wav'; return el.play(); }")
        page.evaluate('removedAudio.remove()')
        page.wait_for_function('removedAudio.paused')
        page.evaluate("switchTab('radio')")
        # A pending job must never restart playback after leaving the tab.
        state['complete'] = False
        page.locator('.station-retro').click()
        page.wait_for_function('radioFillSession === radioSession && !radioPlayer.paused')
        page.evaluate("switchTab('library')")
        state['complete'] = True
        page.wait_for_timeout(3500)
        assert page.evaluate('radioPlayer.paused')
        page.locator('#mini-player-play').click()
        page.get_by_role('button', name='Stop playback', exact=True).click()
        assert page.evaluate('radioPlayer.paused && !radioUserStarted && radioQueue.length === 0')
        assert not errors, errors
        page.screenshot(path=f'/tmp/soundbox-playback-{width}.png')
        print(f'{width}px: interlude, generated next track, exclusive playback, navigation, Stop and geometry passed', flush=True)
        page.close()
    browser.close()
