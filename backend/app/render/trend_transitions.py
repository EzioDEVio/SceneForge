"""Trending short-video transitions (0.9.4-beta.8), built from fast native FFmpeg filters.

xfade's "custom" expressions are evaluated per pixel and took ~3 minutes for one 0.6 s
transition at 1080p, so these are assembled instead from the overlapping pieces:

    A = everything before (ends with the outgoing tail), B = next scene (starts with its head)
    A -> [main][tail]       B -> [head][rest]
    out = concat(main, T(tail, head), rest)     T lasts exactly the transition duration D

which gives the same timing as xfade (offset = start of the tail).

  whip_left / whip_right  fast swipe with motion blur (the "whip pan")
  spin                    A spins and zooms in, B spins out of the zoom
  zoom_punch              punch into the centre of A, land on B pulling back (zoom blur)
  glitch                  jitter, colour split and noise, cut in the middle
  zoom_fade               cinematic crossfade while both pictures drift in scale
  before_after            a white line sweeps across revealing B, like a before/after slider
"""
from __future__ import annotations

NAMES = ("whip_left", "whip_right", "spin", "zoom_punch", "glitch", "zoom_fade", "before_after")


def _ease(x: str) -> str:
    return f"(clip({x},0,1)*clip({x},0,1)*(3-2*clip({x},0,1)))"


def native_graph(kind: str, a: str, b: str, out: str, offset: float, d: float, w: int, h: int, fps: int, uid: str) -> list[str]:
    """Filter-graph parts joining stream labels `a` and `b` into `out` with transition `kind`."""
    u = f"tt{uid}"
    norm = f"fps={fps},format=yuv420p,setsar=1,settb=1/1000000"
    pre = f"fps={fps},format=yuv420p,setsar=1"   # no settb here: zoompan then emitted endless frames
    g = [f"[{a}]split[{u}a1][{u}a2]", f"[{b}]split[{u}b1][{u}b2]",
         f"[{u}a1]trim=end={offset:.4f},setpts=PTS-STARTPTS[{u}main]",
         f"[{u}a2]trim=start={offset:.4f}:duration={d:.4f},setpts=PTS-STARTPTS,{pre}[{u}tail]",
         f"[{u}b1]trim=end={d:.4f},setpts=PTS-STARTPTS,{pre}[{u}head]",
         f"[{u}b2]trim=start={d:.4f},setpts=PTS-STARTPTS[{u}rest]"]
    half = d / 2

    def zoom(z: str) -> str:
        """Centre zoom by factor z (an expression of this piece's own time, it), constant size."""
        return f"zoompan=z='{z}':d=1:s={w}x{h}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

    if kind in ("whip_left", "whip_right"):
        pair = f"[{u}tail][{u}head]" if kind == "whip_left" else f"[{u}head][{u}tail]"
        pos = _ease(f"t/{d:.4f}")
        x = f"(iw-ow)*{pos}" if kind == "whip_left" else f"(iw-ow)*(1-{pos})"
        g += [f"{pair}hstack[{u}strip]",
              # 6 sub-frames per frame, averaged: a smooth motion blur instead of separate ghosts
              f"[{u}strip]fps={fps * 6},crop=w={w}:h={h}:x='{x}':y=0,tmix=frames=6,fps={fps},{norm}[{u}t0]"]
    elif kind == "spin":
        # angle 0 -> 90 deg on A, -90 -> 0 on B; zoom keeps the rotated picture filling the frame
        ang_a = f"PI/2*{_ease(f't/{half:.4f}')}"
        ang_b = f"-PI/2*(1-{_ease(f't/{half:.4f}')})"
        r = max(w, h) / min(w, h)
        cover = lambda ang: f"(abs(cos({ang}))+{r:.4f}*abs(sin({ang})))*1.02"   # zoom that hides the corners
        zoom_a = f"{cover(ang_a.replace('t/', 'it/'))}+0.35*sin(PI*(it/{d:.4f}))"
        zoom_b = f"{cover(ang_b.replace('t/', 'it/'))}+0.35*sin(PI*(0.5+it/{d:.4f}))"
        g += [f"[{u}tail]trim=end={half:.4f},setpts=PTS-STARTPTS,rotate=a='{ang_a}':c=black,{zoom(zoom_a)},tmix=frames=2,{norm}[{u}p1]",
              f"[{u}head]trim=start={half:.4f},setpts=PTS-STARTPTS,rotate=a='{ang_b}':c=black,{zoom(zoom_b)},tmix=frames=2,{norm}[{u}p2]",
              f"[{u}p1][{u}p2]concat=n=2:v=1:a=0[{u}t0]"]
    elif kind == "zoom_punch":
        g += [f"[{u}tail]trim=end={half:.4f},setpts=PTS-STARTPTS,{zoom(f'1+4*pow(it/{d:.4f},2)')},tmix=frames=3,{norm}[{u}p1]",
              f"[{u}head]trim=start={half:.4f},setpts=PTS-STARTPTS,{zoom(f'1+4*pow(1-(0.5+it/{d:.4f}),2)')},tmix=frames=3,{norm}[{u}p2]",
              f"[{u}p1][{u}p2]concat=n=2:v=1:a=0[{u}t0]"]
    elif kind == "glitch":
        shift = max(4, w // 120)
        jit = (f"scale={w * 1.06:.0f}:{h * 1.06:.0f},crop={w}:{h}:x='(iw-{w})/2*(1+sin(n*12.9898))':y='(ih-{h})/2*(1+sin(n*78.233))',"
               f"rgbashift=rh=-{shift}:bh={shift}:gv={shift // 2},noise=alls=22:allf=t")
        g += [f"[{u}tail]trim=end={half:.4f},setpts=PTS-STARTPTS,{jit},{norm}[{u}p1]",
              f"[{u}head]trim=start={half:.4f},setpts=PTS-STARTPTS,{jit},{norm}[{u}p2]",
              f"[{u}p1][{u}p2]concat=n=2:v=1:a=0[{u}t0]"]
    elif kind == "zoom_fade":
        g += [f"[{u}tail]{zoom(f'1+0.12*it/{d:.4f}')},{norm}[{u}za]",
              f"[{u}head]{zoom(f'1.12-0.12*it/{d:.4f}')},{norm}[{u}zb]",
              f"[{u}za][{u}zb]xfade=transition=fade:duration={d:.4f}:offset=0,{norm}[{u}t0]"]
    elif kind == "before_after":
        line = max(4, w // 240)
        # drawbox cannot move over time (its "t" is thickness), so the line is a moving overlay
        g += [f"[{u}tail][{u}head]xfade=transition=wiperight:duration={d:.4f}:offset=0,{norm}[{u}wipe]",
              f"color=c=white:s={line}x{h}:r={fps}:d={d:.4f},format=yuv420p[{u}bar]",
              f"[{u}wipe][{u}bar]overlay=x='W*t/{d:.4f}-{line // 2}':y=0:eof_action=pass,{norm}[{u}t0]"]
    else:
        raise ValueError(f"unknown transition {kind}")
    frames = max(1, round(d * fps))   # exactly the transition length, like xfade
    g.append(f"[{u}t0]tpad=stop_mode=clone:stop={frames},trim=end_frame={frames},setpts=PTS-STARTPTS,{norm}[{u}t]")
    g.append(f"[{u}main][{u}t][{u}rest]concat=n=3:v=1:a=0[{out}]")
    return g
