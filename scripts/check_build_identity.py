#!/usr/bin/env python3
"""Check build identity visibility, hover text and mobile expansion."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', required=True)
parser.add_argument('--html')
parser.add_argument('--manifest')
args = parser.parse_args()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
    for width in (320, 390, 1440):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        if args.html:
            page.route(args.url.rstrip('/') + '/', lambda r: r.fulfill(content_type='text/html', body=Path(args.html).read_text()))
        if args.manifest:
            info = json.loads(Path(args.manifest).read_text())
            page.route('**/static/build-info.json', lambda r: r.fulfill(json=info))
        else:
            info = page.request.get(args.url.rstrip('/') + '/static/build-info.json').json()
        page.goto(args.url, wait_until='networkidle')
        expect(page.locator('#build-label')).to_contain_text(info['build_id'][:8])
        expect(page.locator('#build-label')).to_have_attribute('title', page.locator('#build-details').text_content())
        page.locator('#build-label').click()
        expect(page.locator('#build-details')).to_be_visible()
        expect(page.locator('#build-details')).to_contain_text(info['built_at'])
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        print(json.dumps({'width': width, 'build_id': info['build_id'], 'details': 'passed'}), flush=True)
        page.close()
    browser.close()
