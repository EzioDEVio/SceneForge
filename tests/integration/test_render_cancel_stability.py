"""Repeated real FFmpeg cancellation kills its child, then a render can succeed."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(prefix='sf-cancel-stability-')
os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT/'backend'))
from app.render import ffmpeg_utils as ff
real_popen = ff.subprocess.Popen
for repeat in range(3):
    children=[]
    def capture(*args, **kwargs):
        process=real_popen(*args, **kwargs);children.append(process);return process
    start=time.monotonic()
    with patch.object(ff.subprocess, 'Popen', side_effect=capture):
        try:
            ff.run_ffmpeg(['-re','-f','lavfi','-i','testsrc2=s=320x180:r=25:d=10','-f','null','-'], cancel_check=lambda: time.monotonic()-start>.4)
            raise AssertionError('Cancellation did not stop the render')
        except ff.FFmpegError as exc:
            assert 'cancelled' in str(exc), str(exc)
    assert len(children)==1 and children[0].poll() is not None
    assert time.monotonic()-start<8
    out=Path(tmp.name)/f'retry-{repeat}.mp4'
    ff.run_ffmpeg(['-f','lavfi','-i','color=c=blue:s=320x180:r=25:d=0.2','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(out)])
    assert ff.probe(str(out)).duration_ms>=150
    print(f'PASS cancellation/retry cycle {repeat+1}: no live FFmpeg child, playable retry output', flush=True)
