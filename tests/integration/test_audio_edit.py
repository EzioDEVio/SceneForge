"""Scene audio editing: trim, volume, fades, waveform, remove-without-losing-
picture, and the voice_takes.edit_json upgrade. Verified with real renders."""
import os,pathlib,sys,tempfile,subprocess,sqlite3,time
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
# RC4-era voice_takes table without edit_json must upgrade in place.
db=sqlite3.connect(t/'sceneforge.db')
db.executescript("""CREATE TABLE voice_takes (id VARCHAR(36) PRIMARY KEY, scene_id VARCHAR(36), spoken_text_hash VARCHAR(64), source VARCHAR(32), provider VARCHAR(64), model VARCHAR(64), voice VARCHAR(64), settings_json JSON, audio_asset_id VARCHAR(36), measured_duration_ms INTEGER, accepted BOOLEAN, stale BOOLEAN, created_at DATETIME);
INSERT INTO voice_takes VALUES ('oldtake','nosuchscene','h','upload',NULL,NULL,'Old',NULL,NULL,1234,1,0,'2026-01-01');""")
db.commit();db.close()
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.audio_edit import clean_edit,AudioEditError,effective_ms,narration_filter
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
client=TestClient(app).__enter__()
row=sqlite3.connect(t/'sceneforge.db').execute("select edit_json,measured_duration_ms from voice_takes where id='oldtake'").fetchone()
check('RC4 voice takes upgrade with an empty edit and keep their data',row==('{}',1234))

# --- pure validation -------------------------------------------------------
check('effective length follows trim points',effective_ms(6000,{'in_ms':2000,'out_ms':5000})==3000 and effective_ms(6000,{})==6000 and effective_ms(6000,{'in_ms':1000})==5000)
for bad,why in [({'in_ms':5000,'out_ms':5100},'clips shorter than 0.2 s'),({'in_ms':7000},'start past the end'),({'volume':250},'volume above 200%'),({'fade_in_ms':2000,'fade_out_ms':2000,'in_ms':0,'out_ms':3000},'fades longer than the clip'),({'pitch':3},'unknown settings'),({'in_ms':-5},'negative start')]:
 try:clean_edit(bad,6000);ok=False
 except AudioEditError:ok=True
 check('audio edit rejects '+why,ok)
check('end at the file length is stored as "to the end"',clean_edit({'out_ms':6000},6000)['out_ms'] is None)
check('filter chain trims, levels and fades',narration_filter({'in_ms':2000,'out_ms':5000,'volume':50,'fade_in_ms':500,'fade_out_ms':1000},3000)=='atrim=start=2.000:end=5.000,asetpts=PTS-STARTPTS,volume=0.500,afade=t=in:st=0:d=0.500,afade=t=out:st=2.000:d=1.000' and narration_filter({},1000)=='')

# --- API + real render -----------------------------------------------------
# 6 s source: 2 s of 440 Hz, 2 s silence, 2 s of 880 Hz.
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=f=440:d=2','-f','lavfi','-i','anullsrc=r=44100:cl=mono:d=2','-f','lavfi','-i','sine=f=880:d=2','-filter_complex','[0][1][2]concat=n=3:v=0:a=1','-ar','44100','-ac','1',str(t/'tone.wav')],check=True)
Image.fromarray(np.full((360,640,3),90,dtype='uint8')).save(t/'bg.png')
p=client.post('/api/projects',json={'title':'Audio','aspect':'16:9'}).json();pid=p['id']
img=client.post('/api/assets/upload',params={'project_id':pid},files={'file':('bg.png',open(t/'bg.png','rb'))}).json()
scene=client.post(f'/api/projects/{pid}/scenes',json={'title':'Voice scene'}).json();sid=scene['id']
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':img['id']})
take=client.post(f'/api/scenes/{sid}/voice-takes/upload',files={'file':('tone.wav',open(t/'tone.wav','rb'))}).json()
client.post(f"/api/voice-takes/{take['id']}/select")
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'audio_driven','lead_ms':0,'trail_ms':0})
wave=client.get(f"/api/assets/{take['audio_asset']['id']}/waveform",params={'points':300}).json()
pk=np.array(wave['peaks'])
check('waveform has the requested resolution and the source length',len(pk)==300 and abs(wave['duration_ms']-6000)<50)
check('waveform shows the silent middle',pk[110:190].max()<0.05 and pk[:90].min()>0.5 and pk[210:].min()>0.5)
check('waveform rejects images',client.get(f"/api/assets/{img['id']}/waveform").status_code==415)
def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 sc=client.get(f'/api/projects/{pid}').json()['scenes'][-1]
 path=t/'part.mp4';path.write_bytes(client.get(f"/api/assets/{sc['rendered_asset_id']}/stream").content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','8000','-f','s16le','-'])
 dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))
 return np.frombuffer(raw,dtype=np.int16).astype(float)/32768,dur,sc
def rms(a,s,e):return float(np.sqrt(np.mean(a[int(s*8000):int(e*8000)]**2)))
def freq(a,s,e):
 seg=a[int(s*8000):int(e*8000)];spec=np.abs(np.fft.rfft(seg));return float(np.fft.rfftfreq(seg.size,1/8000)[spec.argmax()])
full,dur,_=render()
check('untrimmed audio renders the whole 6 s',abs(dur-6)<0.1 and rms(full,4.3,5.7)>0.05)
r=client.patch(f"/api/voice-takes/{take['id']}/edit",json={'in_ms':2000})
check('trim saves and reports the trimmed length',r.status_code==200 and r.json()['effective_duration_ms']==4000 and r.json()['edit_json']['in_ms']==2000)
check('editing audio marks the scene for re-render',client.get(f'/api/projects/{pid}').json()['scenes'][-1]['is_stale'])
check('edit endpoint returns a readable reason for bad values',client.patch(f"/api/voice-takes/{take['id']}/edit",json={'volume':900}).json()['detail'].startswith('Volume must be'))
trim,dur,_=render()
check('trimmed scene is 4 s long (Match narration uses the trimmed audio)',abs(dur-4)<0.1)
check('trim starts at the silent section, then plays 880 Hz',rms(trim,0.2,1.8)<0.01 and abs(freq(trim,2.5,3.5)-880)<20)
client.patch(f"/api/voice-takes/{take['id']}/edit",json={'in_ms':0,'out_ms':2000})
loud,dur,_=render()
client.patch(f"/api/voice-takes/{take['id']}/edit",json={'volume':50})
half,_,_=render()
check('trim end cuts the audio to 2 s of 440 Hz',abs(dur-2)<0.1 and abs(freq(loud,0.5,1.5)-440)<20)
check('volume 50% halves the level',abs(rms(half,0.5,1.5)/rms(loud,0.5,1.5)-0.5)<0.05)
client.patch(f"/api/voice-takes/{take['id']}/edit",json={'volume':100,'fade_in_ms':1000,'fade_out_ms':500})
faded,_,_=render()
check('fade in starts quiet and rises',rms(faded,0,0.2)<rms(faded,0.9,1.3)*0.35)
check('fade out ends quiet',rms(faded,1.85,1.98)<rms(faded,1.0,1.4)*0.35)
r=client.patch(f"/api/voice-takes/{take['id']}/edit",json={'in_ms':0,'out_ms':None,'volume':100,'fade_in_ms':0,'fade_out_ms':0}).json()
check('resetting every setting clears the edit',r['edit_json']=={} and r['effective_duration_ms']==6000)
# Remove from scene keeps the picture and the take.
client.post(f'/api/scenes/{sid}/voice-takes/clear-selection')
sc=client.get(f'/api/projects/{pid}').json()['scenes'][-1]
check('removing audio keeps the scene picture and the take',len(sc['shots'])==1 and len(sc['voice_takes'])==1 and not any(v['accepted'] for v in sc['voice_takes']))
check('removed audio stays in the Media Pool',any(a['id']==take['audio_asset']['id'] for a in client.get('/api/assets',params={'project_id':pid}).json()))
print(f'{n} audio edit checks passed')
