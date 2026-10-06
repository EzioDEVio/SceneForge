"""Non-destructive scene excerpts placed on independent project tracks."""
from pathlib import Path
import math, uuid
from app.render.ffmpeg_utils import probe, run_ffmpeg


def clean_free_timeline(raw, project_id, db):
    from app.db.models import Scene
    from app.render.finishing import FinishingError
    if not isinstance(raw, dict) or set(raw)-{'enabled','clips'} or not isinstance(raw.get('enabled'),bool):
        raise FinishingError('Free timeline needs an enabled switch and clips.')
    clips=raw.get('clips',[])
    if not isinstance(clips,list) or len(clips)>128:raise FinishingError('Use up to 128 scene clips.')
    out=[];ids=set()
    for c in clips:
        if not isinstance(c,dict) or set(c)-{'id','scene_id','start_ms','source_in_ms','duration_ms','track'}:raise FinishingError('Unsupported free scene clip setting.')
        ident=c.get('id');scene=db.get(Scene,c.get('scene_id'))
        if not isinstance(ident,str) or not 1<=len(ident)<=80 or ident in ids:raise FinishingError('Each free clip needs a unique id.')
        if not scene or scene.project_id!=project_id:raise FinishingError('Choose a source scene in this project.')
        ids.add(ident);v={'id':ident,'scene_id':scene.id}
        for key,lo,hi in [('start_ms',0,86400000),('source_in_ms',0,86400000),('duration_ms',100,86400000),('track',0,5)]:
            n=c.get(key,0)
            if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n!=int(n) or not lo<=n<=hi:raise FinishingError(f'Free clip {key} must be a whole number from {lo} to {hi}.')
            v[key]=int(n)
        if v['start_ms']+v['duration_ms']>86400000:raise FinishingError('Keep the free timeline within 24 hours.')
        out.append(v)
    return {'enabled':raw['enabled'],'clips':out}


def render_free_timeline(project, scene_paths, cancel_check=None):
    from app.config import RENDERS_DIR
    fin=project.finishing_json or {}; clips=(fin.get('free_timeline') or {}).get('clips',[])
    ends=[c['start_ms']+c['duration_ms'] for c in clips]+[c['start_ms']+c['duration_ms'] for c in fin.get('layer_clips',[])]+[c['start_ms']+c['source_out_ms']-c['source_in_ms'] for c in fin.get('audio_clips',[])]
    duration=max(ends,default=0)/1000
    if duration<=0:raise ValueError('Add a clip to the free timeline before exporting.')
    args=['-y','-f','lavfi','-i',f'color=c=black:s={project.width}x{project.height}:r={project.fps}:d={duration}','-f','lavfi','-i',f'anullsrc=r=48000:cl=stereo:d={duration}']
    graph=[];prev='0:v';audio=['[1:a]']
    from app.db.database import SessionLocal
    from app.db.models import Asset
    from app.config import MEDIA_DIR
    from app.render.layer_clips import text_raster
    items=[{**c,'source_kind':'scene'} for c in clips]+[{**c,'source_kind':'layer'} for c in fin.get('layer_clips',[])]
    # Shared picture tracks: scenes and independent layers use one stacking order.
    with SessionLocal() as db:
        for i,c in enumerate(sorted(items,key=lambda c:-c['track'])):
            source_scene=c['source_kind']=='scene'
            kind='video' if source_scene else c['kind']
            if source_scene:
                path=scene_paths.get(c['scene_id'])
                if not path:raise ValueError('A placed scene has no media. Add media or remove that free clip.')
            elif kind in ('image','video'):
                asset=db.get(Asset,c['asset_id'])
                if not asset or asset.project_id!=project.id:raise ValueError('A free clip has missing or foreign media.')
                path=str(Path(RENDERS_DIR if asset.origin=='render_output' else MEDIA_DIR)/asset.storage_key)
            else:
                path=str(text_raster(c,project.width,project.height))
            begin=c.get('source_in_ms',0)/1000;length=c['duration_ms']/1000;start=c['start_ms']/1000
            info=probe(path)
            if kind=='video' and c.get('source_in_ms',0)+c['duration_ms']>(info.duration_ms or 0)+50:raise ValueError('A free clip extends beyond its source. Trim it after changing the source length.')
            n=i+2
            args+=['-i',str(path)] if kind=='video' else ['-loop','1','-framerate',str(project.fps),'-t',str(duration),'-i',str(path)]
            timing=f'trim=start={begin}:duration={length},setpts=PTS-STARTPTS+{start}/TB,' if kind=='video' else ''
            width=project.width if source_scene else max(2,round(project.width*c['width']/100))
            fx=f'[{n}:v]{timing}scale={width}:-1,setsar=1,fps={project.fps},format=rgba'
            if not source_scene and c['rotation']:
                angle=c['rotation']*math.pi/180
                fx+=f',rotate={angle}:c=none:ow=rotw({angle}):oh=roth({angle})'
            opacity=1 if source_scene else c['opacity']/100
            x=.5 if source_scene else c['x']/100;y=.5 if source_scene else c['y']/100
            graph+=[fx+f',colorchannelmixer=aa={opacity}[s{i}]',f"[{prev}][s{i}]overlay=x=W*{x}-w/2:y=H*{y}-h/2:eof_action=pass:repeatlast=0:enable='gte(t,{start})*lt(t,{start+length})'[v{i}]"]
            prev=f'v{i}'
            if kind=='video' and info.has_audio and (source_scene or not c.get('mute',True)):
                volume=1 if source_scene else c.get('volume',100)/100
                graph.append(f'[{n}:a]atrim=start={begin}:duration={length},asetpts=PTS-STARTPTS,volume={volume},aresample=48000,aformat=channel_layouts=stereo,adelay={c["start_ms"]}:all=1[a{i}]');audio.append(f'[a{i}]')
    graph.append(''.join(audio)+f'amix=inputs={len(audio)}:duration=first:normalize=0,alimiter=limit=.95:level=false:latency=true[aout]')
    out=Path(RENDERS_DIR)/f'free_{project.id}_{uuid.uuid4().hex[:8]}.mp4'
    try:
        run_ffmpeg([*args,'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map',prev if prev=='0:v' else f'[{prev}]','-map','[aout]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-t',str(duration),'-movflags','+faststart',str(out)],cancel_check=cancel_check)
    except BaseException:
        out.unlink(missing_ok=True);raise
    return str(out)
