#!/usr/bin/env python3
"""Browser regression for centered Library pagination and navigation; no writes."""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', required=True)
parser.add_argument('--html', help='Optional rendered HTML preview; API/assets still use --url')
args = parser.parse_args()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
    for width in (1440, 768, 390, 320):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        if args.html:
            page.route(args.url.rstrip('/') + '/', lambda r: r.fulfill(content_type='text/html', body=Path(args.html).read_text()))
        # A multi-page fixture exercises controls even in a small live library.
        sample = page.request.get(args.url.rstrip('/') + '/api/library?per_page=1').json()['items']
        assert sample, 'Requires one existing Library item'
        def library(route):
            number = int(parse_qs(urlsplit(route.request.url).query).get('page', ['1'])[0])
            search = parse_qs(urlsplit(route.request.url).query).get('search')
            route.fulfill(json={'items': [] if search else sample, 'page': number, 'pages': 0 if search else 12, 'per_page': 10, 'total': 0 if search else 120})
        page.route('**/api/library?*', library)
        page.goto(args.url, wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}')
        if width < 600:
            page.locator('#mobile-tab-select').select_option('library')
        else:
            page.locator('#tab-library').click()
        expect(page.locator('#page-info')).to_have_text('Page 1 of 12')
        expect(page.locator('#prev-page')).to_be_disabled()
        page.locator('#next-page').click()
        expect(page.locator('#page-info')).to_have_text('Page 2 of 12')
        page.locator('#prev-page').click()
        expect(page.locator('#page-info')).to_have_text('Page 1 of 12')
        if width > 480:
            page.locator('#page-numbers button').last.click()
            expect(page.locator('#page-info')).to_have_text('Page 12 of 12')
            expect(page.locator('#next-page')).to_be_disabled()
        geometry = page.evaluate('''() => {
            const box = s => document.querySelector(s).getBoundingClientRect();
            const cx = r => r.x + r.width/2, cy = r => r.y + r.height/2;
            const prev=box('#prev-page'), next=box('#next-page'), info=box('#page-info');
            const offsets = ['#prev-page','#next-page'].map(s => {
                const button=box(s), icon=box(s+' svg');
                return [Math.abs(cx(button)-cx(icon)),Math.abs(cy(button)-cy(icon))];
            });
            return {summary:Math.abs(cx(info)-(cx(prev)+cx(next))/2), offsets,
                overflow:document.documentElement.scrollWidth>innerWidth,
                targets:[prev.height,next.height]};
        }''')
        assert geometry['summary'] < 1, geometry
        assert all(max(x) < 1 for x in geometry['offsets']), geometry
        assert min(geometry['targets']) >= 44, geometry
        assert not geometry['overflow'], geometry
        print(json.dumps({'width':width,'geometry':geometry,'navigation':'passed'}), flush=True)
        page.locator('#library-search').fill('unmatched search')
        page.get_by_role('button', name='Clear search and filters', exact=True).click()
        expect(page.locator('#library-search')).to_have_value('')
        expect(page.locator('.library-item').first).to_be_visible()
        page.screenshot(path='/tmp/soundbox-pagination-'+str(width)+'.png', full_page=True)
        page.close()
    browser.close()
