#!/usr/bin/env python3
"""Exercise radio UI lifecycle with mocked jobs; never submit GPU work.
Uses a rendered local template when --html is supplied, otherwise deployed UI.
"""
import argparse
import io
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--html');a=p.parse_args()
track={'id':'a'*32,'filename':'radio-test.wav','prompt':'Ambient test music','model':'music','duration':90,'upvotes':0,'downvotes':0}
buf=io.BytesIO()
with wave.open(buf,'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b'\0\0'*8000*90)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
    for width in (390,1440):
        page=browser.new_page(bypass_csp=True,viewport={'width':width,'height':900});errors=[];fills=[]
        state={'mode':'complete','station':None}
        page.on('pageerror',lambda e:errors.append(str(e)))
        if a.html:
            page.route(a.url.rstrip('/')+'/',lambda r:r.fulfill(content_type='text/html',body=Path(a.html).read_text()))
        page.route('**/api/radio/shuffle?*',lambda r:r.fulfill(json={'tracks':[]}))
        page.route('**/api/radio/next?*',lambda r:r.fulfill(json={'tracks':[]}))
        page.route('**/api/radio/favorites?*',lambda r:r.fulfill(json={'tracks':[]}))
        def fill(r):
            data=r.request.post_data_json;fills.append(data);state['station']=data['station']
            r.fulfill(status=202,json={'job_id':track['id']})
        page.route('**/api/radio/fill',fill)
        def job(r):
            if state['mode']=='failed':r.fulfill(json={'status':'failed','error':'Test model unavailable'})
            elif state['mode']=='waiting':r.fulfill(json={'status':'processing','progress':'Working'})
            else:r.fulfill(json={'status':'completed','filename':track['filename']})
        page.route('**/job/'+track['id'],job)
        page.route('**/api/library/'+track['id'],lambda r:r.fulfill(json=track))
        page.route('**/audio/radio-test.wav',lambda r:r.fulfill(content_type='audio/wav',body=buf.getvalue()))
        page.goto(a.url,wait_until='networkidle')
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}')
        page.wait_for_timeout(500)
        assert not fills, 'Passive page preload must not generate'
        page.locator('.station-ambient').click()
        expect(page.locator('#now-playing #radio-generation-status')).to_contain_text('Creating')
        expect(page.locator('#now-playing')).to_be_visible()
        page.wait_for_function('currentRadioTrack !== null',timeout=12000)
        assert fills[-1]['station']=='ambient'
        # End the last track: the normal media event should extend the station.
        page.evaluate("radioQueue=[]; document.getElementById('radio-player').dispatchEvent(new Event('ended'))")
        page.wait_for_function('radioFillSession !== null')
        page.wait_for_function('currentRadioTrack !== null',timeout=12000)
        assert len(fills)==2 and track['id'] in fills[-1]['exclude']
        state['mode']='waiting'
        page.locator('.station-retro').click()
        expect(page.locator('#radio-generation-status')).to_contain_text('Creating')
        page.locator('.station-favorites').click()
        page.wait_for_timeout(3500)
        assert page.evaluate('currentStation')=='favorites'
        assert page.evaluate('currentRadioTrack') is None
        # Failed generation is visible and does not retry in a loop.
        state['mode']='failed'
        page.locator('.station-piano').click()
        expect(page.locator('#radio-generation-status')).to_contain_text('Test model unavailable',timeout=12000)
        count=len(fills);page.wait_for_timeout(3500);assert len(fills)==count
        state['mode']='waiting'
        page.locator('.station-happy').click()
        page.get_by_role('button',name='Stop radio',exact=True).click()
        state['mode']='complete';page.wait_for_timeout(3500)
        assert page.evaluate('currentRadioTrack') is None
        assert not errors,errors
        print(f'{width}px: passive load, empty station, exhaustion, station switch, failure, integrated empty-library player and Stop passed',flush=True)
        page.close()
    browser.close()
