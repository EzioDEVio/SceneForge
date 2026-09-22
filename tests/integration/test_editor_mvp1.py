"""Isolated real API + FFmpeg regression check. Run from the application root.
Creates a temporary data directory and server; never opens existing user data.
"""
import json, os, pathlib, subprocess, sys, tempfile, time, wave
import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = 'http://127.0.0.1:8137'
results = []

def call(method, path, **kw):
    r = requests.request(method, BASE + path, timeout=30, **kw)
    r.raise_for_status()
    return r.json()

def check(name, cond):
    results.append({'check':name,'passed':bool(cond)})
    print(('PASS ' if cond else 'FAIL ') + name, flush=True)
    if not cond: raise AssertionError(name)

def wait(job_id):
    for _ in range(240):
        j=call('GET','/api/jobs/'+job_id)
        if j['status'] in ['succeeded','failed','cancelled']:
            check('render/export job succeeded',j['status']=='succeeded')
            return j
        time.sleep(.25)
    raise TimeoutError('Render did not complete')

with tempfile.TemporaryDirectory(prefix='sceneforge-mvp1-') as data:
    env={**os.environ,'SCENEFORGE_DATA_DIR':data}
    log=open(pathlib.Path(data)/'server.log','w')
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8137'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log)
    try:
        for _ in range(80):
            try:
                if requests.get(BASE+'/api/health',timeout=1).ok: break
            except requests.RequestException: pass
            time.sleep(.1)
        check('health',call('GET','/api/health')['status']=='ok')
        p=call('POST','/api/projects',json={'title':'Editor MVP1 regression','aspect':'16:9'})
        pid=p['id']; p=call('GET','/api/projects/'+pid)
        check('create/open with three scenes',len(p['scenes'])==3)
        sid=p['scenes'][0]['id']; other=p['scenes'][1]['id']
        spoken='A new chapter in personal computing.'
        caption='بداية الحاسوب الشخصي — 1975'
        s=call('PATCH','/api/scenes/'+sid,json={'original_text':spoken,'spoken_text':spoken,'subtitle_text':caption,'timing_mode':'fixed','requested_duration_ms':2000,'font':{'captions_enabled':True,'size':40}})
        check('separate narration and caption fields',s['spoken_text']==spoken and s['subtitle_text']==caption)
        call('PATCH','/api/scenes/'+sid,json={'spoken_text':spoken+' Updated.'})
        s=call('GET','/api/scenes/'+sid)
        check('narration update preserves captions',s['subtitle_text']==caption)
        check('editing isolated to selected scene',call('GET','/api/scenes/'+other)['original_text']=='')
        with open(ROOT/'examples/fixture_assets/image1.png','rb') as f:
            asset=call('POST',f'/api/assets/upload?project_id={pid}',files={'file':('image1.png',f,'image/png')})
        shot=call('POST',f'/api/scenes/{sid}/shots',json={'asset_id':asset['id']})
        shot=call('PATCH','/api/scenes/shots/'+shot['id'],json={'motion':{'type':'zoom_in'},'fit':'contain'})
        check('media/motion/fit persist',shot['fit']=='contain' and shot['motion_json']['type']=='zoom_in')
        s=call('PATCH','/api/scenes/'+sid,json={'effect_preset':'sepia','font':{'color':'#FFFFFF'}})
        check('font patch preserves family and size',s['font_json']['family']=='Noto Naskh Arabic' and s['font_json']['size']==40)
        audio=pathlib.Path(data)/'narration.wav'
        with wave.open(str(audio),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x00\x00'*48000)
        with open(audio,'rb') as f:
            take=call('POST',f'/api/scenes/{sid}/voice-takes/upload',files={'file':('narration.wav',f,'audio/wav')})
        check('uploaded narration selected',take['accepted'])
        j=wait(call('POST',f'/api/scenes/{sid}/render')['job_id'])
        aid=j['artifact_asset_id']; out=pathlib.Path(data)/'scene.mp4'
        out.write_bytes(requests.get(BASE+f'/api/assets/{aid}/stream',timeout=30).content)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(out)]))
        check('real MP4 has video and audio',{'video','audio'} <= {x['codec_type'] for x in probe['streams']})
        check('fixed duration respected',abs(float(probe['format']['duration'])-2)<.15)
        # Retain a deterministic JSON fixture for browser-only UI tests. No credentials.
        fixture=call('GET','/api/projects/'+pid)
        (ROOT/'tests'/'ui-project-fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2))
        before=call('GET','/api/scenes/'+sid)
        check('render no longer stale',not before['is_stale'])
        call('PATCH','/api/scenes/'+sid,json={'effect_preset':'original'})
        check('effect change marks previous render stale',call('GET','/api/scenes/'+sid)['is_stale'])
        ids=[s['id'] for s in fixture['scenes']]
        call('PUT',f'/api/projects/{pid}/scene-order',json={'scene_ids':list(reversed(ids))})
        check('reordering preserves scene identities',[s['id'] for s in call('GET','/api/projects/'+pid)['scenes']]==list(reversed(ids)))
        for delete_id in ids[1:]: call('DELETE','/api/scenes/'+delete_id)
        exported=wait(call('POST',f'/api/projects/{pid}/export')['job_id'])
        check('export provides downloadable artifact',bool(exported['artifact_asset_id']))
        proc.terminate();proc.wait(timeout=10)
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8137'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log)
        for _ in range(80):
            try:
                if requests.get(BASE+'/api/health',timeout=1).ok: break
            except requests.RequestException: pass
            time.sleep(.1)
        restored=call('GET','/api/projects/'+pid)
        check('project, media, captions and render survive restart',restored['scenes'][0]['subtitle_text']==caption and bool(restored['scenes'][0]['rendered_asset_id']) and len(restored['scenes'][0]['shots'])==1)
        check('unconfigured image provider reports a real error',requests.post(BASE+f'/api/scenes/{sid}/generate-image',json={'prompt':'test'},timeout=10).status_code>=400)
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
        (ROOT/'docs'/'mvp1-test-results.json').write_text(json.dumps(results,indent=2))
print(f'{len(results)} checks passed')
