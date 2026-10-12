#!/usr/bin/env python3
"""Strict browser controls regression; stubs expensive generation, never silently skips controls.
Run against the reviewed deployment. Separate --live test is required for GPU qualification.
"""
import argparse
import json
from playwright.sync_api import sync_playwright, expect

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--url', default='http://localhost:5309')
p.add_argument('--chrome', default='/usr/bin/google-chrome')
a = p.parse_args()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=a.chrome, headless=True, args=['--no-sandbox'])
    for width in (1440, 390):
        page = browser.new_page(viewport={'width': width, 'height': 1000})
        submitted = []
        def generate(route):
            submitted.append(route.request.post_data_json)
            if len(submitted) == 1:
                route.fulfill(json={'success': True, 'job_id': 'browser-regression', 'position': 1})
            else:
                route.fulfill(status=400, json={'success': False, 'error': 'Visible regression rejection'})
        page.route('**/generate', generate)
        page.route('**/job/browser-regression', lambda r: r.fulfill(json={'status':'completed','filename':'regression.wav','quality':{'score':100}}))
        page.route('**/audio/regression.wav', lambda r: r.fulfill(status=204))
        page.route('**/random-prompt', lambda r: r.fulfill(json={'success':True,'prompt':'A quiet piano regression prompt'}))
        page.goto(a.url, wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}')
        if width < 600:
            page.locator('#mobile-tab-select').select_option('generate')
        else:
            page.locator('#tab-generate').first.click()
        # All models and all preset buttons must work, including speech controls.
        for model in ('music', 'audio', 'voice'):
            page.locator('.model-tab[data-model="'+model+'"]').click()
            for chip in page.locator('#'+model+'-examples .chip').all():
                chip.click()
                assert page.locator('#prompt').input_value().strip()
            if model == 'voice':
                for value in ('favorites','en_US','en_GB','all'):
                    page.locator('.voice-filter-btn[data-filter="'+value+'"]').click()
                page.locator('#voice-search').fill('amy')
                page.locator('#voice-search').fill('')
        page.locator('.model-tab[data-model="music"]').click()
        page.locator('#random-btn').click()
        expect(page.locator('#prompt')).to_have_value('A quiet piano regression prompt')
        page.locator('#generate-btn').click()
        expect(page.locator('#player')).to_have_class('player show')
        expect(page.locator('#status')).to_be_hidden()
        # Real clicks submit all music/SFX duration and loop combinations after completion.
        for model in ('music', 'audio'):
            page.locator('.model-tab[data-model="'+model+'"]').click()
            for duration in (3, 60, 120):
                page.locator('#duration').fill(str(duration))
                expect(page.locator('#duration-display')).to_have_text(str(duration))
                for loop in (False, True):
                    if page.locator('#loop-checkbox').is_checked() != loop:
                        page.locator('#loop-control').click()
                    before = len(submitted)
                    page.locator('#generate-btn').click()
                    expect(page.locator('#status')).to_be_visible()
                    expect(page.locator('#status')).to_contain_text('Visible regression rejection')
                    expect(page.locator('#generate-btn')).to_be_enabled()
                    assert len(submitted) == before + 1
                    assert {k: submitted[-1][k] for k in ('model','duration','loop')} == dict(model=model,duration=duration,loop=loop)
        page.locator('#prompt').fill('')
        page.locator('#generate-btn').click()
        expect(page.locator('#status')).to_contain_text('Please enter a description')
        print(json.dumps({'width':width,'submissions':len(submitted),'presets':'passed','filters':'passed','repeat_after_success':'passed'}),flush=True)
        page.close()
    browser.close()
