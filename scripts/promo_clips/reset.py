"""Put the demo project back into a known state before each recording."""
import requests, copy
B='http://127.0.0.1:8765'; PID='47a481e2-e3f5-4275-a7c3-95ad54e7df51'
def project(): return requests.get(f'{B}/api/projects/{PID}').json()
def scene(title): return next(s for s in project()['scenes'] if s['title']==title)
def patch_scene(sid, **body):
    r=requests.patch(f'{B}/api/scenes/{sid}', json=body); r.raise_for_status(); return r.json()
def no_markers():
    p=project(); fin=p['finishing_json']; fin['timeline']['markers']=[]
    requests.patch(f'{B}/api/projects/{PID}', json={'finishing':fin}).raise_for_status()
def golden_title():
    s=scene('Golden hour'); font=copy.deepcopy(s['font_json'])
    for l in font.get('layers',[]):
        if l.get('text')=='NIGHT CITY':
            l.pop('keyframes',None); l.update(x=50,y=22,size=150,rotation=0,opacity=100)
    patch_scene(s['id'], font=font)
if __name__=='__main__':
    no_markers(); golden_title(); print('reset ok')
