// Pure-logic checks for keyframe interpolation (src/keyframes.ts, mirrored by
// backend/app/render/keyframes.py) and live-playback segment planning (src/SequencePlayer.tsx).
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
await build({stdin:{contents:"export * from './src/keyframes';export {liveSegments,segmentAt,liveStatus,previewMixKey} from './src/SequencePlayer';export {sequenceClips} from './src/ProjectTimeline';",resolveDir:'.',loader:'ts'},outfile:'node_modules/.cache/keyframes.cjs',bundle:true,platform:'node',format:'cjs',external:['react','react-dom','lucide-react'],logLevel:'silent'});
const require=createRequire(import.meta.url);
const K=require('../node_modules/.cache/keyframes.cjs');
let passed=0;const check=(name,cond)=>{assert.ok(cond,name);console.log('PASS '+name);passed++;};
const near=(a,b,e=1e-6)=>Math.abs(a-b)<=e;

check('easing curves start at 0, end at 1 and differ in between',['linear','ease_in','ease_out','ease_in_out'].every(e=>K.ease(e,0)===0&&near(K.ease(e,1),1))&&near(K.ease('ease_in',.5),.25)&&near(K.ease('ease_out',.5),.75)&&near(K.ease('ease_in_out',.5),.5)&&near(K.ease('linear',.3),.3));
check('easing clamps progress outside 0..1',K.ease('linear',-2)===0&&K.ease('ease_in',3)===1);
const kfs=[{t_ms:1000,x:30,ease:'ease_in'},{t_ms:0,x:10},{t_ms:2000,x:50}];
check('values hold before the first and after the last keyframe (unsorted input)',K.valueAt(kfs,'x',0,-100)===10&&K.valueAt(kfs,'x',0,5000)===50);
check('linear segment interpolates halfway',near(K.valueAt(kfs,'x',0,500),20));
check('the ease belongs to the segment leaving the keyframe',near(K.valueAt(kfs,'x',0,1500),35));
check('a missing value falls back to the layer value',near(K.valueAt([{t_ms:0},{t_ms:1000,y:80}],'y',40,500),60));
check('no keyframes: the base value',K.valueAt(undefined,'x',42,100)===42&&K.valueAt([],'x',42,100)===42);
check('a single keyframe overrides the base value everywhere',K.valueAt([{t_ms:500,opacity:20}],'opacity',100,0)===20);

const ov={id:'o',asset_id:'a',x:50,y:50,width:20,rotation:0,opacity:100,start_ms:1000,end_ms:null};
check('overlays without keyframes are returned unchanged (same object)',K.overlayAt(ov,1500)===ov);
const kov={...ov,keyframes:[{t_ms:0,x:20,opacity:0,width:10,rotation:0},{t_ms:2000,x:80,opacity:100,width:30,rotation:90}]};
const mid=K.overlayAt(kov,2000);
check('overlay keyframe times are relative to the overlay start',near(mid.x,50)&&near(mid.opacity,50)&&near(mid.width,20)&&near(mid.rotation,45)&&mid.y===50);
check('before the overlay starts the first keyframe holds',K.overlayAt(kov,0).x===20);
const tl={id:'t',text:'Hi',x:30,y:40,size:60,start_ms:0,end_ms:0,keyframes:[{t_ms:0,size:60},{t_ms:1000,size:120,rotation:30,opacity:40}]};
const t=K.textLayerAt(tl,500);
check('text layers interpolate size, rotation (from 0) and opacity (from 100)',near(t.size,90)&&near(t.rotation,15)&&near(t.opacity,70)&&t.x===30);
check('text layers without keyframes are unchanged',K.textLayerAt({...tl,keyframes:undefined},500).size===60);

let list=K.upsertKeyframe([], {t_ms:500,x:1});
list=K.upsertKeyframe(list,{t_ms:100,x:2});
check('upsert keeps keyframes sorted and defaults the ease to linear',list.map(k=>k.t_ms).join()==='100,500'&&list[0].ease==='linear');
list=K.upsertKeyframe(list,{t_ms:520,x:9});
check('upsert near an existing keyframe replaces it and keeps its time',list.length===2&&list[1].t_ms===500&&list[1].x===9);
let full=[];for(let i=0;i<40;i++)full=K.upsertKeyframe(full,{t_ms:i*100,x:i});
check('at most 32 keyframes',full.length===K.MAX_KEYFRAMES&&K.MAX_KEYFRAMES===32);
check('remove deletes by time',K.removeKeyframe(list,100).map(k=>k.t_ms).join()==='500');
const cap=K.captureKeyframe({x:12.345,y:50,width:20,rotation:0,opacity:100,radius:4},K.OVERLAY_KEYS,1234.6,'ease_out');
check('capture records only the animated properties, rounded, at a whole ms',cap.t_ms===1235&&cap.x===12.35&&cap.ease==='ease_out'&&!('radius' in cap));
check('edits on an un-keyframed layer change the layer directly',JSON.stringify(K.keyframedPatch(ov,{x:10},K.OVERLAY_KEYS,ov,1500))===JSON.stringify({x:10}));
const p=K.keyframedPatch(kov,{x:70,border:3},K.OVERLAY_KEYS,K.overlayAt(kov,1500),1500);
check('edits on a keyframed layer go to a keyframe at the playhead; other fields pass through',p.border===3&&!('x' in p)&&p.keyframes.length===3&&p.keyframes[1].t_ms===500&&p.keyframes[1].x===70&&near(p.keyframes[1].opacity,25));

// live playback planning
const shot={id:'s',asset_id:'img',asset:{id:'img',type:'image'},source_in_ms:0};
const sc=(id,extra={})=>({id,title:id,shots:[shot],voice_takes:[],timing_mode:'fixed',requested_duration_ms:2000,lead_ms:0,trail_ms:0,transition_in_json:{type:'cut',duration_ms:0},rendered_asset_id:'r'+id,is_stale:false,revision:1,font_json:{},...extra});
const scenes=[sc('a'),sc('b',{transition_in_json:{type:'dissolve',duration_ms:500}}),sc('c',{rendered_asset_id:null}),sc('d',{is_stale:true}),sc('e',{shots:[]})];
const project={id:'p',scenes,finishing_json:{}};
const segs=K.liveSegments(project,K.sequenceClips(scenes));
check('scene status: rendered, unrendered, stale and empty',segs.map(s=>s.status).join()==='ready,ready,unrendered,stale,empty');
check('rendered scenes stream their preview media; others have none',segs[0].url.startsWith('/api/scenes/a/preview-media?v=ra%3A')&&segs[2].url===null&&segs[3].url===null);
check('unrendered scenes show a still of their first picture',segs[2].still==='/api/assets/img/thumbnail?w=960');
check('transitions become hard cuts at the next scene start',segs[0].cutAt===segs[1].start&&segs[1].start===1500&&segs[0].end===2000);
check('the last segment plays to its end',segs.at(-1).cutAt===segs.at(-1).end);
check('segmentAt finds the scene playing at a time (the incoming scene owns the overlap)',K.segmentAt(segs,0)===0&&K.segmentAt(segs,1499)===0&&K.segmentAt(segs,1500)===1&&K.segmentAt(segs,99999)===4);
check('preview key changes when the timeline audio changes',K.previewMixKey(project,scenes[0])!==K.previewMixKey({...project,finishing_json:{audio_clips:[{id:'x'}]}},scenes[0]));
console.log(`${passed} keyframe and playback unit checks passed`);
