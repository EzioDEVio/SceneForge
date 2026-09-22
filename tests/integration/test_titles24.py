"""Real FFmpeg frames verify title animation, not just saved settings."""
import io,os,pathlib,sys,tempfile,time,subprocess
from PIL import Image,ImageStat
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project

def job(c,id):
 for _ in range(600):
  j=c.get('/api/jobs/'+id).json()
  if j['status']=='failed':raise AssertionError(j['error'])
  if j['status']=='succeeded':return j
  time.sleep(.1)
 raise AssertionError('render timeout')
def bright(path,t):
 data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
 image=Image.open(io.BytesIO(data)).convert('L');return ImageStat.Stat(image).mean[0]
with TestClient(app) as c:
 p=c.post('/api/projects',json={'title':'Titles','aspect':'16:9'}).json()
 with SessionLocal() as db:
  obj=db.get(Project,p['id']);obj.width=640;obj.height=360;db.commit()
 p=c.get('/api/projects/'+p['id']).json();sid=p['scenes'][0]['id']
 buf=io.BytesIO();Image.new('RGB',(640,360),'black').save(buf,format='PNG')
 asset=c.post('/api/assets/upload?project_id='+p['id'],files={'file':('black.png',buf.getvalue(),'image/png')}).json()
 c.post(f'/api/scenes/{sid}/shots',json={'asset_id':asset['id'],'motion':{'type':'static'}}).raise_for_status()
 for mode in ['fade','slide','typewriter']:
  layer={'id':'title','text':'بداية الحكاية','x':50,'y':50,'size':64,'color':'#FFFFFF','bold':True,'animation':mode,'animation_ms':800}
  c.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000,'font':{'captions_enabled':False,'layers':[layer]}}).raise_for_status()
  j=job(c,c.post(f'/api/scenes/{sid}/render').json()['job_id']);f=pathlib.Path(tmp.name)/(mode+'.mp4');f.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
  early,late=bright(f,.03),bright(f,1.0)
  assert late>early+0.2,(mode,early,late)
  print('PASS',mode,'Arabic rendered frames',round(early,3),round(late,3))
