import io,json,time,wave
from playwright.sync_api import sync_playwright,expect
import argparse
from urllib.parse import urlencode
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radio_generation import STATIONS
parser=argparse.ArgumentParser(description='Opt-in real 90-second radio qualification; adds one public track.')
parser.add_argument('--url',required=True)
parser.add_argument('--station',default='dreamy',choices=list(STATIONS))
parser.add_argument('--run-generation',action='store_true')
parser.add_argument('--output',default='/tmp/soundbox-live-radio.json')
a=parser.parse_args()
if not a.run_generation:raise SystemExit('Requires --run-generation: adds one public radio track')
url=a.url.rstrip('/')
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
 page=b.new_page(bypass_csp=True,viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(url,wait_until='networkidle');page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}')
 ready_deadline=time.monotonic()+180
 while page.request.get(url+'/status').json()['models'].get('music') not in ('ready','available'):
  if time.monotonic()>ready_deadline:raise TimeoutError('Music model not ready')
  page.wait_for_timeout(3000)
 assert page.request.get(url+'/api/radio/shuffle?'+urlencode({'model':'music','search':STATIONS[a.station][0]})).json()['tracks']==[], 'Choose an empty station for this qualification'
 with page.expect_response(lambda r:r.url.endswith('/api/radio/fill') and r.request.method=='POST') as reply:
  page.locator('.station-'+a.station).click()
 response=reply.value;body=response.json();print('SUBMITTED',response.status,body,flush=True)
 assert response.status==202,body
 job=body['job_id']
 shared=page.request.post(url+'/api/radio/fill',data={'station':a.station});assert shared.status==202 and shared.json()['job_id']==job
 print('SHARED',shared.json(),flush=True)
 deadline=time.monotonic()+1800
 while time.monotonic()<deadline:
  result=page.request.get(url+'/job/'+job).json()
  print(json.dumps({k:result.get(k) for k in ('status','progress','error')}),flush=True)
  assert result['status'] not in ['failed','cancelled'],result
  if result['status']=='completed':break
  page.wait_for_timeout(10000)
 else:raise TimeoutError(job)
 page.wait_for_function('(id)=>currentRadioTrack?.id===id && !radioPlayer.paused && radioPlayer.currentTime > 0',arg=job,timeout=15000)
 audio=page.request.get(url+'/audio/'+result['filename']);assert audio.ok
 with wave.open(io.BytesIO(audio.body())) as wav:duration=wav.getnframes()/wav.getframerate()
 assert 89<=duration<=91,duration
 record=page.request.get(url+'/api/library/'+job).json();assert record['is_public']
 assert not errors,errors
 page.screenshot(path='/tmp/soundbox-live-radio.png',full_page=True)
 receipt={'job':job,'duration':duration,'bytes':len(audio.body()),'public':record['is_public'],'browser_playback':True,'shared_job':True}
 open(a.output,'w').write(json.dumps(receipt,indent=2));print('VERIFIED',receipt,flush=True)
 b.close()
