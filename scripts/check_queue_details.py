#!/usr/bin/env python3
"""Check queue descriptions, escaped prompts and wrapping without submitting jobs."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--html')
args = parser.parse_args()
prompt = 'Layered piano with a gentle melody and evolving strings. ' * 20 + '<script>unsafe()</script>'
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
    page = browser.new_page(bypass_csp=True)
    if args.html:
        page.route(args.url.rstrip('/') + '/', lambda r: r.fulfill(
            content_type='text/html', body=Path(args.html).read_text()))
    page.route('**/api/queue', lambda r: r.fulfill(json={'total': 2, 'jobs': [
        dict(id='a' * 32, prompt=prompt, model='music', duration=90, status='processing',
             position=1, progress='Generating music... 25%', progress_pct=25,
             radio_station='piano', loop=True),
        dict(id='b' * 32, prompt='An owl calling in the forest', model='audio', duration=15,
             status='queued', position=2, progress_pct=0, radio_station=None, loop=False)
    ]}))
    page.goto(args.url, wait_until='networkidle')
    page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
    page.evaluate("switchTab('generate'); document.getElementById('server-status-card').classList.remove('collapsed'); loadQueueExplorer()")
    expect(page.locator('#queue-explorer-list .queue-item')).to_have_count(2)
    expect(page.locator('#queue-explorer-list .queue-item').first).to_contain_text('Radio · piano')
    expect(page.locator('#queue-explorer-list .queue-item').first).to_contain_text('Loop enabled')
    expect(page.locator('#queue-explorer-list .queue-item').nth(1)).to_contain_text('Sound effects')
    expect(page.locator('#queue-explorer-list .queue-item').nth(1)).to_contain_text('Waiting')
    assert page.locator('#queue-explorer-list .queue-item script').count() == 0
    for width in (320, 390, 768, 1440):
        page.set_viewport_size({'width': width, 'height': 900})
        assert page.locator('.server-status-header').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
        for opened in (False, True):
            page.locator('.queue-description').first.evaluate('(el, value) => el.open = value', opened)
            page.locator('#queue-explorer-list .queue-item').first.scroll_into_view_if_needed()
            assert page.locator('#queue-explorer-list').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
            assert page.locator('#queue-explorer-list .queue-item').first.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
        expect(page.locator('.queue-full-prompt').first).to_have_text(prompt)
        page.locator('.queue-description').first.evaluate('(el) => el.open = false')
        page.screenshot(path=f'/tmp/soundbox-queue-{width}.png')
        print(f'{width}px: public generation details, prompt expansion and bounds passed', flush=True)
    browser.close()
