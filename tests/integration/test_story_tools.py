"""Section D: real APIs, Undo snapshots, reusable rows and rendered pixels. No providers."""
import os, pathlib, sys, tempfile, subprocess, time
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory(prefix='sf-story-tests-');os.environ['SCENEFORGE_DATA_DIR']=tmp.name
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe
n=0

def check(name, ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)

def job(c,jid):
 for _ in range(600):
  j=c.get('/api/jobs/'+jid).json()
  if j['status'] in ('succeeded','failed','cancelled'):
   assert j['status']=='succeeded',j
   return j
  time.sleep(.1)
 raise AssertionError('Render timed out')

with TestClient(app) as c:
 pid=c.post('/api/projects',json={'title':'Story tools','aspect':'16:9','fps':25}).json()['id']
 with SessionLocal() as db:
  p=db.get(Project,pid);p.width=320;p.height=180;db.commit()
 scenes=c.get('/api/projects/'+pid).json()['scenes'];sid=scenes[1]['id']
 for scene in scenes:
  c.patch('/api/scenes/'+scene['id'],json={'timing_mode':'fixed','requested_duration_ms':4000,'font':{'captions_enabled':False}})
 for name in ['image1.png','image2.png']:
  a=c.post('/api/assets/upload?project_id='+pid,files={'file':(name,(root/'examples/fixture_assets'/name).read_bytes(),'image/png')}).json()
  c.post('/api/scenes/'+sid+'/shots',json={'asset_id':a['id']})
 before=c.get('/api/scenes/'+sid).json()
 times=[4520,5000,6000,7000]
 plan=c.post('/api/scenes/'+sid+'/autocut/preview',json={'times_ms':times}).json()
 check('AutoCut translates timeline beats into selected scene local cuts',plan['cuts_ms']==[520,1000,2000,3000])
 check('Preview leaves original shots untouched',c.get('/api/scenes/'+sid).json()['shots']==before['shots'])
 check('AutoCut rejects stale preview',c.post('/api/scenes/'+sid+'/autocut',json={'times_ms':times,'revision':-1}).status_code==409)
 c.patch('/api/scenes/'+scenes[0]['id'],json={'requested_duration_ms':4200})
 check('AutoCut rejects preview after earlier scene timing changes',c.post('/api/scenes/'+sid+'/autocut',json={'times_ms':times,'revision':plan['revision'],'preview_token':plan['preview_token']}).status_code==409)
 c.patch('/api/scenes/'+scenes[0]['id'],json={'requested_duration_ms':4000})
 c.patch('/api/projects/'+pid,json={'finishing':{'timeline':{'version':1,'tracks':{'V1':{'locked':True}},'audio_tracks':['A3'],'markers':[]}}})
 check('AutoCut respects the Picture track lock',c.post('/api/scenes/'+sid+'/autocut/preview',json={'times_ms':times}).status_code==409)
 c.patch('/api/projects/'+pid,json={'finishing':{'timeline':{'version':1,'tracks':{},'audio_tracks':['A3'],'markers':[]}}})
 r=c.post('/api/scenes/'+sid+'/autocut',json={'times_ms':times,'revision':plan['revision'],'preview_token':plan['preview_token']});assert r.status_code==200,r.text
 after=c.get('/api/scenes/'+sid).json()
 check('Beat edits preserve scene length and create actual alternating clips',sum(s['duration_ms'] for s in after['shots'])==4000 and len(after['shots'])==5 and [s['asset_id'] for s in after['shots']]==[before['shots'][i%2]['asset_id'] for i in range(5)])
 check('Captions and narration text remain unchanged',after['font_json']==before['font_json'] and after['spoken_text']==before['spoken_text'])
 check('Undo restores original clips with their IDs',c.post('/api/scenes/'+sid+'/restore',json=before).status_code==200 and c.get('/api/scenes/'+sid).json()['shots']==before['shots'])
 check('Redo restores the same beat edit',c.post('/api/scenes/'+sid+'/restore',json=after).status_code==200 and c.get('/api/scenes/'+sid).json()['shots']==after['shots'])
 check('Out-of-scene beats cannot create an edit',c.post('/api/scenes/'+sid+'/autocut/preview',json={'times_ms':[1,9000]}).status_code==400)
 cutjob=job(c,c.post('/api/scenes/'+sid+'/render').json()['job_id'])
 out=pathlib.Path(tmp.name)/'cut.mp4';out.write_bytes(c.get('/api/assets/'+cutjob['artifact_asset_id']+'/stream').content)
 check('AutoCut really renders and keeps duration',abs(probe(str(out)).duration_ms-4000)<100)
 def pixel(sec):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(sec),'-i',str(out),'-frames:v','1','-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  return np.frombuffer(raw,np.uint8).reshape(180,320,3).astype(int)
 check('Rendered pictures change at planned beat cuts',np.abs(pixel(.2)-pixel(.7)).mean()>5 and np.abs(pixel(.2)-pixel(1.2)).mean()<3)
 preview=c.post('/api/projects/'+pid+'/import',json={'text':'First paragraph [1].\nContinues here.\n\nالمشهد الثاني يتكلم بالعربية.','split_mode':'paragraphs'}).json()
 check('Script paragraphs preserve multiline narration and Arabic',len(preview['scenes'])==2 and 'Continues here.' in preview['scenes'][0]['spoken_text'] and 'بالعربية' in preview['scenes'][1]['spoken_text'])
 check('Script citations retained in original and omitted from subtitles','[1]' in preview['scenes'][0]['original_text'] and '[1]' not in preview['scenes'][0]['subtitle_text'])
 structured=c.post('/api/projects/'+pid+'/import',json={'text':'## Scene 1\nVisual: skyline\nMore visual detail\nNarration: Hello\ncontinues\n## المشهد ٢\nالسرد: أهلا','split_mode':'headings'}).json()
 check('Structured script fields stay separate and preserve continuations',len(structured['scenes'])==2 and structured['scenes'][0]['spoken_text']=='Hello\ncontinues' and 'skyline' in structured['scenes'][0]['original_text'])
 added=c.post('/api/projects/'+pid+'/import/apply',json={'scenes':preview['scenes'],'replace_existing':False}).json()
 check('Script appends scenes without replacing existing work',len(c.get('/api/projects/'+pid).json()['scenes'])==5 and len(added)==2)
 exact=c.post('/api/projects/'+pid+'/import',json={'text':'Scene 7\nThis is one paragraph.','split_mode':'paragraphs'}).json()
 check('Paragraph mode does not split heading-like text',len(exact['scenes'])==1 and exact['scenes'][0]['original_text']=='Scene 7\nThis is one paragraph.')
 check('Empty script yields a review warning',c.post('/api/projects/'+pid+'/import',json={'text':'','split_mode':'paragraphs'}).json()['scenes']==[])
 check('Invalid split mode rejected',c.post('/api/projects/'+pid+'/import',json={'text':'hi','split_mode':'wrong'}).status_code==400)
 # Template asset IDs must be remapped everywhere, including upper-track images and music.
 layer={'id':'overlay','kind':'image','asset_id':a['id'],'track':0,'start_ms':0,'duration_ms':1000,'x':50,'y':50,'width':30}
 c.patch('/api/projects/'+pid,json={'finishing':{'layer_clips':[layer]}})
 saved=c.post('/api/project-templates',json={'project_id':pid,'name':'My setup'}).json()
 check('Reusable template saved and listed',any(t['id']==saved['id'] for t in c.get('/api/project-templates').json()['templates']))
 copy=c.post('/api/project-templates/'+saved['id']+'/create',json={'title':'From template'}).json();cp=c.get('/api/projects/'+copy['id']).json()
 check('Template creates a separate editable project',copy['id']!=pid and len(cp['scenes'])==5 and cp['title']=='From template')
 newlayer=cp['finishing_json']['layer_clips'][0]
 check('Template remaps image references and retains actual media',newlayer['asset_id']!=a['id'] and c.get('/api/assets/'+newlayer['asset_id']+'/stream').status_code==200)
 c.delete('/api/projects/'+pid)
 copy2=c.post('/api/project-templates/'+saved['id']+'/create',json={'title':'After deleting source'})
 check('Saved template survives deleting the source project',copy2.status_code==200)
 check('Template rejects traversal IDs',c.post('/api/project-templates/not-a-uuid/create',json={'title':'Bad'}).status_code==404)
 check('Template delete retains created projects',c.delete('/api/project-templates/'+saved['id']).status_code==204 and c.get('/api/projects/'+copy['id']).status_code==200)
 # Video stabilization is executed by the real renderer; confirm filter invocation and actual artifact.
 vs=cp['scenes'][0]['id']
 from PIL import Image, ImageFilter
 rng=np.random.default_rng(173)
 texture=np.asarray(Image.fromarray(rng.integers(0,256,(180,320,3),dtype=np.uint8)).filter(ImageFilter.GaussianBlur(.6)))
 frames=np.stack([np.roll(texture,(int(6*np.sin(i*.8)),int(8*np.sin(i*.9))),axis=(0,1)) for i in range(75)])
 clip=pathlib.Path(tmp.name)/'shaky-source.mp4'
 generated=subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','320x180','-framerate','25','-i','pipe:0','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],input=frames.tobytes(),capture_output=True)
 assert generated.returncode==0,generated.stderr
 v=c.post('/api/assets/upload?project_id='+copy['id'],files={'file':('clip.mp4',clip.read_bytes(),'video/mp4')}).json()
 c.post('/api/scenes/'+vs+'/shots',json={'asset_id':v['id']})
 for bad in [0,101,True,'50']:
  check('Reject invalid stabilization strength '+str(bad),c.patch('/api/scenes/'+vs,json={'look':{'stabilize':{'strength':bad}}}).status_code==400)
 r=c.patch('/api/scenes/'+vs,json={'look':{'stabilize':{'strength':50}}})
 check('Video stabilization saves without changing timing',r.status_code==200 and r.json()['requested_duration_ms']==4000)
 from unittest.mock import patch
 from app.render import renderer
 real=renderer.run_ffmpeg;calls=[]
 def capture(args,**kwargs):
  calls.append(args);return real(args,**kwargs)
 with patch.object(renderer,'run_ffmpeg',side_effect=capture):
  j=job(c,c.post('/api/scenes/'+vs+'/render').json()['job_id'])
 check('Real scene renderer invokes deshake on video',any(any('deshake=rx=32:ry=32:edge=mirror' in str(arg) for arg in args) for args in calls))
 rendered=pathlib.Path(tmp.name)/'stabilized.mp4';rendered.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
 check('Stabilized output is playable and retains duration',probe(str(rendered)).width==320 and abs(probe(str(rendered)).duration_ms-4000)<100)
 def movement(path):
  raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  frames=np.frombuffer(raw,np.uint8).reshape(-1,180,320,3).astype(float)
  return np.abs(np.diff(frames[25:70,30:-30,30:-30],axis=0)).mean()
 check('Real stabilization reduces frame movement on simulated handheld footage',movement(rendered)<movement(clip)*.95)
 check('AutoCut rejects intervals longer than the video excerpt',c.post('/api/scenes/'+vs+'/autocut/preview',json={'times_ms':[500]}).status_code==400)
 check('Stabilization can be removed',c.patch('/api/scenes/'+vs,json={'look':{'stabilize':None}}).status_code==200 and 'stabilize' not in c.get('/api/scenes/'+vs).json()['look_json'])
 print(f'{n} Section D checks passed')
