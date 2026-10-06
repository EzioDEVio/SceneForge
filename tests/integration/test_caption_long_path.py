"""Caption render regression for deep data folders, quotes and concurrent jobs.

Runs real FFmpeg on Linux; the Windows libass MAX_PATH case still needs a
Windows retest. No models or paid providers are used.
"""
from pathlib import Path
import sys
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.render import renderer
from app.render.ffmpeg_utils import run_ffmpeg, probe, FFmpegError


def main():
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sf-caption-path-") as temp:
        parent = Path(temp)
        # The real report's ASS pathname was 279 characters. Apostrophes in
        # user folder names must also stay outside the filter expression.
        for index in range(5):
            parent /= "Deep SceneForge folder's name " + str(index) + "x" * 28
        parent.mkdir(parents=True)
        visual = parent / 'visual.mp4'
        run_ffmpeg(['-f', 'lavfi', '-i', 'color=c=black:s=320x180:r=25:d=1',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(visual)])
        project = SimpleNamespace(aspect='16:9', width=320, height=180)
        seen = []

        def checked_ffmpeg(args, **kwargs):
            if '-vf' in args:
                graph = args[args.index('-vf') + 1]
                assert "ass='captions.ass'" in graph, graph
                assert str(parent) not in graph, graph
                assert kwargs.get('cwd'), 'Caption subprocess must use an isolated working folder'
                staged = Path(kwargs['cwd']) / 'captions.ass'
                assert staged.is_file()
                assert len(str(staged)) < 260, 'The staged caption input must be a short path'
                seen.append(kwargs['cwd'])
            return run_ffmpeg(args, **kwargs)

        def render(name, cancel=False):
            work = parent / name
            work.mkdir()
            scene = SimpleNamespace(id='scene', subtitle_text='Caption ' + name,
                font_json={'captions_enabled': True, 'family': 'Noto Sans', 'size': 36,
                    'caption_segments': [{'text': 'Caption ' + name, 'start_ms': 0, 'end_ms': 900}],
                    'layers': [{'text': 'TITLE', 'kind': 'text', 'start_ms': 0,
                        'end_ms': 1000, 'family': 'Noto Sans', 'size': 30, 'x': 50, 'y': 20}]},
                voice_takes=[])
            assert len(str(work / 'scene_captions.ass')) > 279
            out = renderer.mux_audio_and_captions(scene, project, str(visual), 1000,
                None, 0, work, renderer.RenderContext(cancel_requested=cancel))
            assert Path(out).is_file()
            assert 900 <= probe(out).duration_ms <= 1100
            assert 'Caption ' + name in (work / 'scene_captions.ass').read_text()
            # Successful encoding must also contain visible caption/title pixels.
            from app.config import FFMPEG_BIN
            import numpy as np
            pixels = subprocess.check_output([FFMPEG_BIN, '-v', 'error', '-i', out,
                '-ss', '0.5', '-frames:v', '1', '-threads', '1', '-f', 'rawvideo',
                '-pix_fmt', 'rgb24', 'pipe:1'])
            frame = np.frombuffer(pixels, dtype=np.uint8).reshape(180, 320, 3)
            assert (frame[:80].max(axis=2) > 180).sum() > 20, 'Title must appear in rendered pixels'
            assert (frame[80:].max(axis=2) > 180).sum() > 20, 'Caption must appear in rendered pixels'
            return out

        with patch.object(renderer, 'run_ffmpeg', side_effect=checked_ffmpeg):
            with ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(render, ['one', 'two']))
        assert len(set(outputs)) == len(set(seen)) == 2
        assert all(not Path(folder).exists() for folder in seen), 'Temporary caption copies must be cleaned'
        assert Path.cwd() == original_cwd, 'Rendering must never change global cwd'
        print('PASS real caption + title renders from >279-character paths with apostrophes')
        print('PASS simultaneous subtitle jobs use separate working folders and preserve process cwd')
        print('PASS staged subtitle paths stay below 260 characters and are cleaned after rendering')
        with patch.object(renderer, 'run_ffmpeg', side_effect=checked_ffmpeg):
            try:
                render('cancelled', cancel=True)
                raise AssertionError('Cancellation must stop rendering')
            except FFmpegError as exc:
                assert 'cancelled' in str(exc)
        assert all(not Path(folder).exists() for folder in seen)
        assert Path.cwd() == original_cwd
        print('PASS cancellation stops caption rendering and removes its temporary subtitle copy')


if __name__ == '__main__':
    main()
