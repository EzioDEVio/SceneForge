"""MVP1.1: real audio/video verification using isolated data and deterministic fixtures.
Run from app root. Optional first argument: a typewriter MP3 to test custom upload.
Requires the app dependencies plus numpy and Pillow for decoded-media assertions.
"""
import array,json,os,pathlib,sqlite3,subprocess,sys,tempfile,time,wave
import requests
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.render.typewriter import reveal_schedule,graphemes,write_typing_audio,DEFAULT_KEY
BASE='http://127.0.0.1:8138';checks=[]
OUT=ROOT/'docs'/'mvp1.1-evidence';OUT.mkdir(exist_ok=True)
def check(name,ok,detail=None):
    checks.append({'check':name,'passed':bool(ok),'detail':detail})
    print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok:raise AssertionError(name)
def call(method,path,**kwargs):
    r=requests.request(method,BASE+path,timeout=30,**kwargs);r.raise_for_status();return r.json()
def wait_server():
    for _ in range(100):
        try:
            if requests.get(BASE+'/api/health',timeout=1).ok:return
        except requests.RequestException:pass
        time.sleep(.1)
    raise TimeoutError('Server startup failed')
def render(sid):
    j=call('POST',f'/api/scenes/{sid}/render')
    for _ in range(600):
        r=call('GET','/api/jobs/'+j['job_id'])
        if r['status'] in ('failed','cancelled'):raise AssertionError(r.get('error'))
        if r['status']=='succeeded':return r['artifact_asset_id']
        time.sleep(.1)
    raise TimeoutError('Render timeout')
def download(aid,path):path.write_bytes(requests.get(BASE+f'/api/assets/{aid}/stream',timeout=30).content)
def decode_audio(path):
    b=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','s16le','-ac','1','-ar','48000','-'])
    return np.frombuffer(b,dtype='<i2').astype(float)/32768
def frame(path,t):
    b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    return np.frombuffer(b,dtype=np.uint8).reshape(360,640,3)
try:
    check('Arabic combining marks kept with base',graphemes('عَرَبِيّ')==['عَ','رَ','بِ','يّ'])
    check('emoji ZWJ and flag preserved',len(graphemes('👩‍💻🇮🇶'))==2)
    sched=reveal_schedule('A B',4000,{'typewriter_delay_ms':500,'typewriter_duration_ms':1500})
    check('one schedule preserves silent whitespace',[(e['time_ms'],e['sound']) for e in sched]==[(500,True),(1250,False),(2000,True)])
    check('long captions get strictly increasing nonempty events',all(b['time_ms']>a['time_ms'] for a,b in zip(reveal_schedule('a'*5000,1000,{}),reveal_schedule('a'*5000,1000,{})[1:])))
    with tempfile.TemporaryDirectory(prefix='sceneforge-sync-') as data:
        env={**os.environ,'SCENEFORGE_DATA_DIR':data}
        log=open(pathlib.Path(data)/'server.log','w')
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8138'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log)
        try:
            wait_server()
            p=call('POST','/api/projects',json={'title':'MVP1.1 preview and sound','aspect':'16:9'});pid=p['id']
            with sqlite3.connect(pathlib.Path(data)/'sceneforge.db') as db:db.execute('UPDATE projects SET width=640,height=360 WHERE id=?',(pid,))
            p=call('GET','/api/projects/'+pid);scenes=p['scenes'];sid=scenes[0]['id']
            image=Image.new('RGB',(300,500),(20,110,80));draw=ImageDraw.Draw(image);draw.rectangle((0,0,299,499),outline=(240,40,30),width=20)
            im=pathlib.Path(data)/'portrait.png';image.save(im)
            with open(im,'rb') as f:asset=call('POST',f'/api/assets/upload?project_id={pid}',files={'file':('portrait.png',f,'image/png')})
            custom=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_KEY
            with open(custom,'rb') as f:sound=call('POST',f'/api/assets/upload?project_id={pid}',files={'file':(custom.name,f,'audio/mpeg' if custom.suffix=='.mp3' else 'audio/wav')})
            check('custom typing recording uploads as audio',sound['type']=='audio')
            other=call('POST','/api/projects',json={'title':'Other project','aspect':'16:9'})
            other=call('GET','/api/projects/'+other['id'])
            r=requests.patch(BASE+'/api/scenes/'+other['scenes'][0]['id'],json={'font':{'typewriter_sound_asset_id':sound['id']}},timeout=10)
            check('sound cannot reference another project',r.status_code==400)
            check('invalid typing volume rejected',requests.patch(BASE+'/api/scenes/'+sid,json={'font':{'typewriter_volume':999}},timeout=10).status_code==400)
            texts=['A B','مَرْحَبًا','Hello عالم']
            videos=[]
            for i,s in enumerate(scenes):
                s_id=s['id']
                shot=call('POST',f'/api/scenes/{s_id}/shots',json={'asset_id':asset['id'],'fit':'contain','motion':{'type':'static'}})
                font={'captions_enabled':True,'typewriter':True,'typewriter_sound':True,'typewriter_delay_ms':500,'typewriter_duration_ms':1500,'typewriter_volume':60,'family':'Noto Naskh Arabic','size':40,'position':'middle'}
                if i==1:font['typewriter_sound_asset_id']=sound['id']
                call('PATCH','/api/scenes/'+s_id,json={'subtitle_text':texts[i],'timing_mode':'fixed','requested_duration_ms':4000,'font':font})
                aid=render(s_id);v=OUT/f'typewriter-{i+1}.mp4';download(aid,v);videos.append(v)
                audio=decode_audio(v)
                schedule=reveal_schedule(texts[i],4000,font)
                check(f'{i+1}: no typing audio before start delay',np.max(np.abs(audio[:int(.46*48000)]))<.002)
                check(f'{i+1}: typing clicks follow every audible reveal',all(np.max(np.abs(audio[int(e['time_ms']*48):int(e['time_ms']*48)+2400]))>.015 for e in schedule if e['sound']))
                check(f'{i+1}: sound ends after final keystroke',np.max(np.abs(audio[int(2.2*48000):]))<.002)
                check(f'{i+1}: clip has exact four-second duration',abs(len(audio)/48000-4)<.05)
                if i==0:
                    a=frame(v,.3);b=frame(v,.7)
                    check('contain renders black side bars',a[:,0:100].mean()<3 and a[:,540:].mean()<3)
                    check('contain preserves red top/bottom border',a[5,320,0]>170 and a[354,320,0]>170)
                    check('captions appear after synchronized delay',np.abs(a[100:260].astype(float)-b[100:260]).sum()>2000)
                    check('whitespace reveal has no audio click',np.max(np.abs(audio[int(1.20*48000):int(1.40*48000)]))<.002)
                    call('PATCH','/api/scenes/shots/'+shot['id'],json={'fit':'cover'})
                    check('fit change invalidates render',call('GET','/api/scenes/'+s_id)['is_stale'])
                    call('PATCH','/api/scenes/'+s_id,json={'font':{'typewriter_sound':False}})
                    cover=pathlib.Path(data)/'cover.mp4';download(render(s_id),cover)
                    check('cover fills frame with no side bars',frame(cover,.3)[:,0:80,1].mean()>40)
                    check('sound switch off produces silent output without narration',np.max(np.abs(decode_audio(cover)))<.002)
                    call('PATCH','/api/scenes/shots/'+shot['id'],json={'fit':'contain'})
                    call('PATCH','/api/scenes/'+s_id,json={'font':{'typewriter_sound':True}})
            # Use a known tone as narration, then verify mixing and removal without deleting the take.
            tone=pathlib.Path(data)/'voice.wav'
            with wave.open(str(tone),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
                w.writeframes((np.sin(2*np.pi*440*np.arange(192000)/48000)*2000).astype('<i2').tobytes())
            with open(tone,'rb') as f:take=call('POST',f'/api/scenes/{sid}/voice-takes/upload',files={'file':('voice.wav',f,'audio/wav')})
            mixed=pathlib.Path(data)/'mixed.mp4';download(render(sid),mixed);aud=decode_audio(mixed)
            check('narration and typing both mix without clipping',np.max(np.abs(aud))<.99 and np.sqrt(np.mean(aud[3*48000:3*48000+4800]**2))>.01)
            call('POST',f'/api/scenes/{sid}/voice-takes/clear-selection')
            check('clear narration preserves take for reuse',len(call('GET','/api/scenes/'+sid)['voice_takes'])==1 and not call('GET','/api/scenes/'+sid)['voice_takes'][0]['accepted'])
            export=call('POST',f'/api/projects/{pid}/export')
            for _ in range(600):
                j=call('GET','/api/jobs/'+export['job_id'])
                if j['status']=='succeeded':break
                if j['status']=='failed':raise AssertionError(j['error'])
                time.sleep(.1)
            check('multi-scene export succeeds',j['status']=='succeeded')
            exported=OUT/'typewriter-full-export.mp4';download(j['artifact_asset_id'],exported)
            a=decode_audio(exported)
            check('export preserves each scene sound offset',all(np.max(np.abs(a[int((offset+.5)*48000):int((offset+.56)*48000)]))>.015 for offset in (0,4,8)))
            check('export preserves silent scene lead-ins',all(np.max(np.abs(a[int((offset+.05)*48000):int((offset+.4)*48000)]))<.002 for offset in (0,4,8)))
            (OUT/'schedule-example.json').write_text(json.dumps(sched,ensure_ascii=False,indent=2))
        finally:proc.terminate();proc.wait(timeout=10);log.close()
finally:(OUT/'test-results.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(f'{len(checks)} checks passed')
