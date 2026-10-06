"""Real FFmpeg regression: centered zooms must not drift under easing."""
import pathlib, subprocess, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'backend'))
from app.render.filters import resolve_motion, build_cover_motion_chain, EASINGS
for kind in ('zoom_in', 'zoom_out', 'close_up'):
    for easing in EASINGS:
        plan = resolve_motion({'type': kind})
        plan.easing = easing
        chain = build_cover_motion_chain(plan, 160, 90, 12, 12)
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            'color=black:s=320x180:r=12:d=1,drawbox=x=158:y=0:w=4:h=180:color=white:t=fill,drawbox=x=0:y=88:w=320:h=4:color=white:t=fill',
            '-vf', chain, '-frames:v', '12', '-threads', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
        frames = np.frombuffer(raw, dtype=np.uint8).reshape(12, 90, 160, 3)
        for frame in frames:
            y, x = np.where(frame[:,:,0] > 210)
            assert abs(x.mean() - 79.5) < 2 and abs(y.mean() - 44.5) < 2, (kind, easing, x.mean(), y.mean())
        print('PASS centered', kind, easing)
print('12 real-render motion checks passed')
