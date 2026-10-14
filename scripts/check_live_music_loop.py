#!/usr/bin/env python3
"""Opt-in real GPU/browser qualification: one 120-second looped music request."""
import argparse
import io
import json
import time
import wave
from playwright.sync_api import sync_playwright, expect

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--url',required=True)
p.add_argument('--run-generation',action='store_true')
p.add_argument('--output',default='/tmp/soundbox-live-loop.json')
a=p.parse_args()
if not a.run_generation:raise SystemExit('Requires --run-generation: this creates a real public audio track')
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=b.new_page(viewport={'width':390,'height':844})
 page.goto(a.url,wait_until='networkidle');page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}');page.locator('#mobile-tab-select').select_option('generate')
 page.locator('.model-tab[data-model="music"]').click()
 page.locator('#prompt').fill('Gentle ambient piano and soft synthesizer pads, steady slow rhythm, seamless background music, no vocals')
 page.locator('#duration').fill('120')
 if not page.locator('#loop-checkbox').is_checked():page.locator('#loop-control').click()
 with page.expect_response(lambda r:r.url.endswith('/generate') and r.request.method=='POST') as reply:
  page.locator('#generate-btn').click()
 response=reply.value;body=response.json();print('Submission',response.status,body,flush=True)
 assert response.status==200 and body['success']
 assert reply.value.request.post_data_json['duration']==120 and reply.value.request.post_data_json['loop'] is True
 job=body['job_id'];deadline=time.monotonic()+1800
 while time.monotonic()<deadline:
  result=page.request.get(a.url+'/job/'+job).json()
  print(json.dumps({k:result.get(k) for k in ('id','status','progress','retry_count','error')}),flush=True)
  if result['status']=='failed':raise AssertionError(result)
  if result['status']=='completed':break
  page.wait_for_timeout(10000)
 else:raise TimeoutError('Generation exceeded 30-minute qualification budget; inspect job before retrying')
 expect(page.locator('#player')).to_have_class('player show',timeout=15000)
 audio=page.request.get(a.url+'/audio/'+result['filename']);assert audio.ok
 with wave.open(io.BytesIO(audio.body())) as wav:
  duration=wav.getnframes()/wav.getframerate()
  assert 118<=duration<=121,duration
 library=page.request.get(a.url+'/api/library?per_page=100').json()
 assert any(x['id']==job for x in library['items'])
 page.locator('#mobile-tab-select').select_option('library')
 expect(page.locator('.library-item[data-id="'+job+'"]').first).to_be_visible(timeout=15000)
 receipt=dict(job_id=job,duration_seconds=duration,audio_bytes=len(audio.body()),public_library=True,browser_player=True,result=result)
 with open(a.output,'w') as f:json.dump(receipt,f,indent=2)
 print('VERIFIED',json.dumps(receipt),flush=True);b.close()
