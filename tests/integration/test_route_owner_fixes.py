"""Decode real route overlays: endpoints, reversals, edge labels and shared artwork."""
import pathlib,sys,tempfile,subprocess
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'backend'))
from app.render.routes import clean_route,route_clip,_label_font
assert _label_font('London',12).size==12
assert _label_font('لندن',12).size==12
with tempfile.TemporaryDirectory(prefix='sf-route-owner-') as cache:
 def frames(route):
  path=route_clip(clean_route(route),640,360,10,pathlib.Path(cache))
  raw=subprocess.check_output(['ffmpeg','-v','error','-i',path,'-threads','1','-pix_fmt','rgba','-f','rawvideo','-'])
  return np.frombuffer(raw,np.uint8).reshape(-1,360,640,4)
 for marker in ('none','dot','plane','ship','car','pin'):
  for reverse in (False,True):
   points=[[12,94],[50,45],[89,3]];labels=['Spain','Rome','London']
   if reverse:points.reverse();labels.reverse()
   route={'points':points,'labels':labels,'draw_ms':1000,'marker':marker}
   rendered=frames(route);baseline=frames({**route,'labels':[]})
   # Readable origin on frame zero, destination on the final draw frame, all three thereafter.
   for k in range(3):
    f=0 if k==0 else 9 if k==2 else 13
    delta=np.any(rendered[f]!=baseline[f],axis=2)
    x=int(points[k][0]*6.4);y=int(points[k][1]*3.6)
    area=delta[max(0,y-48):min(360,y+48),max(0,x-65):min(640,x+65)]
    assert area.sum()>100,(marker,reverse,labels[k],f,area.sum())
   # Destination is visible even when the scene ends before the route reaches it.
   delta=np.any(rendered[0]!=baseline[0],axis=2);x=int(points[-1][0]*6.4);y=int(points[-1][1]*3.6)
   assert delta[max(0,y-48):min(360,y+48),max(0,x-65):min(640,x+65)].sum()>100
   # Icon dimensions must not leak into label font size. Labels remain small and within the frame.
   delta=np.any(rendered[-1]!=baseline[-1],axis=2)
   rows=np.flatnonzero(delta.any(axis=1));assert len(rows)<110,(marker,rows)
   assert not delta[0].any() and not delta[-1].any(),(marker,reverse)
   print('PASS real route labels',marker,'reverse' if reverse else 'forward',flush=True)
 route={'points':[[2,99],[98,99]],'labels':['Long destination label near frame edge','لندن'],'draw_ms':1000,'marker':'plane'}
 rendered=frames(route);assert rendered[-1,:,:,3].any()
 if len(sys.argv)>1:
  output=pathlib.Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
  route={'points':[[15,72],[48,48],[85,28]],'labels':['Spain','Rome','London'],'draw_ms':1000,'marker':'plane'}
  frame=Image.fromarray(frames(route)[-1]);background=Image.new('RGBA',frame.size,(35,49,68,255));background.alpha_composite(frame);background.convert('RGB').save(output/'route-three-stops.png')
 print('PASS long and Arabic edge labels; source font resolution')
