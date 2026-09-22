"""Combined beta checks. Real API/FFmpeg; external image and TTS responses are fixtures."""
import base64, io, json, os, pathlib, sqlite3, subprocess, sys, tempfile, threading, time, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
import requests
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.providers.gemini_image import generate_image
from app.providers.openai_image import ImageProviderError
from app.render.typewriter import reveal_schedule
from app.providers.local_offline_tts import synthesize as basic_speech
checks=[]
def check(name, condition):
    checks.append({'check':name,'passed':bool(condition)})
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    assert condition,name
image=io.BytesIO();Image.new('RGB',(640,360),(35,90,120)).save(image,'PNG');png=image.getvalue()
with patch('app.providers.gemini_image.requests.post') as post:
    post.return_value=SimpleNamespace(ok=True,json=lambda:{'steps':[{'type':'model_output','content':[{'type':'image','data':base64.b64encode(png).decode()}]}]})
    check('Gemini extracts actual binary image from response',generate_image('fixture-key','test','1536x1024','fixture-model')==png)
    payload=post.call_args.kwargs
    check('Gemini key stays in header and aspect uses documented response format',payload['headers']['x-goog-api-key']=='fixture-key' and payload['json']['response_format']['aspect_ratio']=='3:2')
    post.return_value=SimpleNamespace(ok=True,json=lambda:{'steps':[{'text':'blocked'}]})
    try:generate_image('fixture-key','test','1024x1024','fixture-model');ok=False
    except ImageProviderError:ok=True
    check('Gemini no-image response is actionable error',ok)
with tempfile.TemporaryDirectory() as tmp:
    target=pathlib.Path(tmp)/'speech.wav';target.touch()
    with patch('app.providers.local_offline_tts.subprocess.run') as runner:
        runner.return_value=SimpleNamespace(returncode=0,stderr=b'')
        basic_speech('مرحبا بكم في قصتنا.',str(target),voice='ar')
        check('offline diagnostic receives full sentence as UTF-8, not individual letters',runner.call_args.kwargs['input']=='مرحبا بكم في قصتنا.'.encode('utf-8') and '--stdin' in runner.call_args.args[0])
check('default typewriter is slower for long captions',reveal_schedule('abcdefghijklmnopqrstuvwxyz',10000,{})[-1]['time_ms']==4000)
# A real HTTP endpoint returning deterministic audio tests adapter routing without downloaded models.
audio=io.BytesIO()
with wave.open(audio,'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
    samples=(np.sin(np.arange(24000)*2*np.pi*220/24000)*6000).astype('<i2');w.writeframes(samples.tobytes())
received=[]
class VoiceService(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'{"voices":[{"id":"af_heart"},{"id":"default"}]}')
    def do_POST(self):
        received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(200);self.send_header('Content-Type','audio/wav');self.end_headers();self.wfile.write(audio.getvalue())
server=ThreadingHTTPServer(('127.0.0.1',0),VoiceService)
threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:8139'
def call(method,path,**kw):
    r=requests.request(method,base+path,timeout=30,**kw);r.raise_for_status();return r.json()
def job(j):
    for _ in range(600):
        result=call('GET','/api/jobs/'+j['job_id'])
        if result['status']=='failed':raise AssertionError(result['error'])
        if result['status']=='succeeded':return result['artifact_asset_id']
        time.sleep(.1)
    raise TimeoutError('Job did not complete')
def frame(path,t):
    data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    return np.frombuffer(data,dtype=np.uint8).reshape(360,640,3)
try:
 with tempfile.TemporaryDirectory(prefix='sceneforge-combined-') as tmp:
    tmp=pathlib.Path(tmp)
    with open(tmp/'server.log','w') as log:
      proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--port','8139'],cwd=ROOT/'backend',env={**os.environ,'SCENEFORGE_DATA_DIR':str(tmp)},stdout=log,stderr=log)
      try:
        for _ in range(100):
            try:
                if requests.get(base+'/api/health',timeout=1).ok:break
            except requests.RequestException:pass
            time.sleep(.1)
        p=call('POST','/api/projects',json={'title':'Combined beta test'})
        pid=p['id']
        with sqlite3.connect(tmp/'sceneforge.db') as db:db.execute('UPDATE projects SET width=640,height=360 WHERE id=?',(pid,))
        scenes=call('GET','/api/projects/'+pid)['scenes'];sid=scenes[0]['id']
        res=requests.post(base+f'/api/projects/{pid}/export?skip_empty=true',timeout=10)
        check('all-empty export rejected before creating a job',res.status_code==400 and 'at least one' in res.text)
        asset=call('POST',f'/api/assets/upload?project_id={pid}',files={'file':('fixture.png',png,'image/png')})
        for s in scenes[:2]:
            call('POST',f'/api/scenes/{s["id"]}/shots',json={'asset_id':asset['id']})
            call('PATCH',f'/api/scenes/{s["id"]}',json={'timing_mode':'fixed','requested_duration_ms':2000,'font':{'captions_enabled':False}})
        res=requests.post(base+f'/api/projects/{pid}/export',timeout=10)
        check('empty scene export gives clear preflight error',res.status_code==400 and 'Part-3' in res.text)
        profiles={}
        for cap,name in [('image','openai'),('image','gemini'),('speech','kokoro'),('speech','chatterbox')]:
            profiles[name]=call('POST','/api/providers',json={'capability':cap,'name':name,'api_key':'fixture-key' if cap=='image' else '', 'base_url':f'http://127.0.0.1:{server.server_port}','model':name})
        connected=call('POST','/api/local-speech/kokoro/connect')
        check('local speech component connects without cloud key entry',connected['status']=='service_reachable' and connected['profile']['id']==profiles['kokoro']['id'])
        check('backend exposes matching release identity',call('GET','/api/health')['build']=='workspace-2.5')
        check('four independent provider profiles coexist',len(call('GET','/api/providers'))==4)
        call('POST','/api/providers',json={'capability':'image','name':'gemini','api_key':'fixture-key','model':'new-model'})
        check('editing Gemini preserves OpenAI profile',len(call('GET','/api/providers'))==4 and next(p for p in call('GET','/api/providers') if p['name']=='openai')['id']==profiles['openai']['id'])
        check('voice discovery reaches local HTTP service',call('GET',f'/api/providers/profile/{profiles["kokoro"]["id"]}/voices')['voices']==['af_heart','default'])
        call('PATCH',f'/api/scenes/{sid}',json={'spoken_text':'Hello world'})
        body={'provider_id':profiles['kokoro']['id'],'voice':'af_heart','language':'en','speed':.8,'audition':True}
        audition=call('POST',f'/api/scenes/{sid}/voice-takes/service',json=body)
        check('natural voice audition returns playable asset without selecting a take',audition['asset']['duration_ms']==1000 and not call('GET',f'/api/scenes/{sid}')['voice_takes'])
        body['audition']=False
        take=call('POST',f'/api/scenes/{sid}/voice-takes/service',json=body)
        check('natural narration creates accepted persistent take',take['accepted'] and take['provider']=='kokoro')
        check('speaking speed and voice sent to service',received[-1]['speed']==.8 and received[-1]['voice']=='af_heart')
        call('PATCH',f'/api/scenes/{sid}',json={'spoken_text':'مرحبا بالعالم'})
        res=requests.post(base+f'/api/scenes/{sid}/voice-takes/service',json=body,timeout=10)
        check('Arabic Kokoro request prevented with alternative guidance',res.status_code==502 and 'Chatterbox' in res.text)
        body.update(provider_id=profiles['chatterbox']['id'],voice='default',language='ar')
        take=call('POST',f'/api/scenes/{sid}/voice-takes/service',json=body)
        check('Chatterbox Arabic routing and one accepted take',received[-1]['language']=='ar' and sum(t['accepted'] for t in call('GET',f'/api/scenes/{sid}')['voice_takes'])==1)
        layer={'id':'title','text':'TITLE مرحبا','x':50,'y':50,'size':54,'color':'#FFFFFF','start_ms':500,'end_ms':1400,'bold':True}
        call('PATCH',f'/api/scenes/{sid}',json={'font':{'layers':[layer]}})
        res=requests.patch(base+f'/api/scenes/{sid}',json={'font':{'layers':[{**layer,'x':101}]}},timeout=10)
        check('invalid text coordinates rejected',res.status_code==400)
        video=tmp/'layer.mp4';aid=job(call('POST',f'/api/scenes/{sid}/render'));video.write_bytes(requests.get(base+f'/api/assets/{aid}/stream',timeout=20).content)
        before,during,after=[frame(video,t) for t in [.2,.8,1.7]]
        check('text overlay appears only inside timing window',np.mean(np.abs(during.astype(float)-before))>1 and np.mean(np.abs(after.astype(float)-before))<.3)
        for effect in ['glitch','film_grain','high_contrast','faded','dream','cinematic','noir','sharpen','negative']:
            call('PATCH',f'/api/scenes/{scenes[1]["id"]}',json={'effect_preset':effect,'effect_intensity':100})
            aid=job(call('POST',f'/api/scenes/{scenes[1]["id"]}/render'))
            check(effect+' renders actual media',bool(aid))
            if effect=='glitch':
                video=tmp/'glitch.mp4';video.write_bytes(requests.get(base+f'/api/assets/{aid}/stream',timeout=20).content)
                check('glitch changes over time on a static image',np.mean(np.abs(frame(video,.1).astype(float)-frame(video,.4)))>1)
        for transition in ['cut','dissolve','fade_through_black','fade_white','slide','slide_right','wipe_left','wipe_right','circle_open']:
            call('PATCH',f'/api/scenes/{scenes[1]["id"]}',json={'transition_in':{'type':transition,'duration_ms':300}})
            aid=job(call('POST',f'/api/projects/{pid}/export?skip_empty=true'))
            video=tmp/'export.mp4';video.write_bytes(requests.get(base+f'/api/assets/{aid}/stream',timeout=20).content)
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(video)]))
            check(f'{transition} export skips empty scene and mixes narrated/silent scenes',abs(float(info['format']['duration'])-(4 if transition=='cut' else 3.7))<.12)
        deleted=call('DELETE',f'/api/projects/{pid}')
        check('populated project deletes with scenes, jobs and assets',deleted['ok'] and requests.get(base+f'/api/projects/{pid}').status_code==404)
        call('DELETE',f'/api/providers/profile/{profiles["gemini"]["id"]}')
        check('removing one image provider keeps the other',any(p['name']=='openai' for p in call('GET','/api/providers')))
      finally:
        proc.terminate();proc.wait(timeout=10)
finally:
 server.shutdown()
 out=ROOT/'docs'/'combined-evidence';out.mkdir(exist_ok=True)
 (out/'results.json').write_text(json.dumps(checks,indent=2))
print(f'{len(checks)} combined checks passed')
