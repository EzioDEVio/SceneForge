"""Run against source OR the actual packaged executable. Auth, UI, FFmpeg and exit."""
import argparse,json,os,pathlib,queue,subprocess,sys,tempfile,threading,time,urllib.request,urllib.error
parser=argparse.ArgumentParser();parser.add_argument('--exe');parser.add_argument('--resources',required=True);parser.add_argument('--ffmpeg-dir',required=True);args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];token='a'*64
with tempfile.TemporaryDirectory() as tmp:
 data=pathlib.Path(tmp)/'workspace';env={**os.environ,'SCENEFORGE_DESKTOP_TOKEN':token,'SCENEFORGE_DATA_DIR':str(data),'SCENEFORGE_RESOURCE_DIR':args.resources,'SCENEFORGE_SD_AUTOSTART':'0'}
 ext='.exe' if os.name=='nt' else ''
 env['SCENEFORGE_FFMPEG']=str(pathlib.Path(args.ffmpeg_dir)/('ffmpeg'+ext));env['SCENEFORGE_FFPROBE']=str(pathlib.Path(args.ffmpeg_dir)/('ffprobe'+ext))
 command=[args.exe] if args.exe else [sys.executable,str(root/'backend/desktop_entry.py')]
 with open(pathlib.Path(tmp)/'stderr.log','w+') as log:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,env=env,text=True)
  try:
   lines=queue.Queue()
   def reader():
    for line in p.stdout:lines.put(line)
    lines.put('EXIT')
   threading.Thread(target=reader,daemon=True).start()
   deadline=time.time()+60;origin=None
   while time.time()<deadline:
    try:line=lines.get(timeout=1)
    except queue.Empty:continue
    if line.startswith('SCENEFORGE_READY '):origin='http://127.0.0.1:'+str(json.loads(line[17:])['port']);break
    if line=='EXIT':break
   if not origin:
    log.seek(0);raise AssertionError(log.read())
   def request(path,body=None,auth=True,origin_header=None):
    headers={'Content-Type':'application/json'}
    if auth:headers['X-SceneForge-Token']=token
    if origin_header:headers['Origin']=origin_header
    r=urllib.request.Request(origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    return urllib.request.urlopen(r,timeout=90)
   for path in ['/api/health','/']:
    try:request(path,auth=False);raise AssertionError('Unauthenticated access permitted')
    except urllib.error.HTTPError as e:assert e.code==403
   try:request('/api/health',origin_header='https://untrusted.example');raise AssertionError('Foreign origin permitted')
   except urllib.error.HTTPError as e:assert e.code==403
   assert json.load(request('/api/health'))['status']=='ok'
   assert b'<html' in request('/').read().lower()
   project=json.load(request('/api/projects',{'title':'Desktop smoke','aspect':'16:9'}));assert project['id']
   payload={'text':'Desktop Alpha بداية الحكاية','background':'#000000','duration':1,'layer':{'id':'test','text':'Title','animation':'fade','animation_ms':200}}
   media=request('/api/title-preview',payload).read();assert len(media)>1000
   out=pathlib.Path(tmp)/'title.mp4';out.write_bytes(media)
   info=json.loads(subprocess.check_output([env['SCENEFORGE_FFPROBE'],'-v','error','-show_format','-of','json',str(out)]));assert .9<float(info['format']['duration'])<1.2
   p.stdin.close();assert p.wait(timeout=10)==0
   assert (data/'sceneforge.db').exists()
   print('PASS packaged backend authentication, origin checks, frontend, persistent project, Arabic FFmpeg preview and parent-exit shutdown')
  finally:
   if p.poll() is None:p.kill();p.wait()
