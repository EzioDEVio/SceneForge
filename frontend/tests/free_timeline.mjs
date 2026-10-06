import {build} from 'esbuild';import {createRequire} from 'node:module';import assert from 'node:assert/strict';import {JSDOM} from 'jsdom';
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost'});globalThis.window=dom.window;globalThis.document=dom.window.document;
await build({entryPoints:['src/FreeTimeline.tsx'],outfile:'node_modules/.cache/free-timeline.cjs',bundle:true,platform:'node',format:'cjs',external:['react'],logLevel:'silent'});
const require=createRequire(import.meta.url),{moveFree,cutFreeRange,freeItems,splitFreeAt}=require('../node_modules/.cache/free-timeline.cjs');
const p={scenes:[{id:'source',title:'Editable source'}],finishing_json:{free_timeline:{enabled:true,clips:[{id:'scene',scene_id:'source',start_ms:1000,source_in_ms:400,duration_ms:2000,track:3}]},layer_clips:[{id:'picture',kind:'video',asset_id:'v',start_ms:1000,source_in_ms:1000,duration_ms:2000,track:2}],audio_clips:[{id:'voice',asset_id:'a',name:'Audio',start_ms:1000,source_in_ms:1000,source_out_ms:3000,fade_in_ms:100,fade_out_ms:100,track:'A4',censor:[{start_ms:1700,end_ms:1800,mode:'bleep'}]}]}};
const original=JSON.stringify(p),keys=freeItems(p).map(c=>c.key);let moved=moveFree(p,keys,500,1);assert.equal(moved.free_timeline.clips[0].start_ms,1500);assert.equal(moved.free_timeline.clips[0].track,4);assert.equal(moved.layer_clips[0].track,3);assert.equal(moved.audio_clips[0].track,'A5');assert.equal(moved.audio_clips[0].source_in_ms,1000);
moved=moveFree(p,keys,-9000,-9);assert.equal(moved.free_timeline.clips[0].start_ms,0);assert.equal(moved.audio_clips[0].track,'A3');assert.equal(moved.free_timeline.clips[0].track,2);
const cut=cutFreeRange(p,keys,1500,2200);assert.equal(cut.selected.length,3);assert.deepEqual(cut.patch.free_timeline.clips.map(c=>[c.start_ms,c.source_in_ms,c.duration_ms]),[[1000,400,500],[1500,900,700],[2200,1600,800]]);assert.deepEqual(cut.patch.layer_clips.map(c=>c.source_in_ms),[1000,1500,2200]);assert.deepEqual(cut.patch.audio_clips.map(c=>[c.source_in_ms,c.source_out_ms]),[[1000,1500],[1500,2200],[2200,3000]]);assert.equal(cut.patch.audio_clips[1].fade_in_ms,0);assert.equal(cut.patch.audio_clips[1].fade_out_ms,0);assert.deepEqual(cut.patch.audio_clips[1].censor,p.finishing_json.audio_clips[0].censor);assert.throws(()=>cutFreeRange(p,keys,1050,2000),/0.1 seconds/);assert.equal(JSON.stringify(p),original);console.log('PASS free scene/video/audio group bounds, range excerpts, source offsets, fades/censor preservation and immutable source');

const q={...p,fps:30};
assert.equal(splitFreeAt(q,['scene:scene'],1099).count,1);
assert.throws(()=>splitFreeAt({...q,fps:24},['scene:scene'],1101),/0.1 seconds/);
const first=splitFreeAt(q,keys,1500);
assert.equal(first.count,3);assert.equal(first.selected.length,3);
assert.deepEqual(first.patch.free_timeline.clips.map(c=>[c.start_ms,c.source_in_ms,c.duration_ms]),[[1000,400,500],[1500,900,1500]]);
const next=splitFreeAt({...q,finishing_json:{...q.finishing_json,...first.patch}},first.selected,2200);
assert.equal(next.count,3);assert.deepEqual(next.patch.free_timeline.clips.map(c=>c.duration_ms),[500,700,800]);
assert.equal(next.patch.audio_clips[2].source_in_ms,2200);
assert.equal(splitFreeAt(q,[],1500).count,3);
assert.throws(()=>splitFreeAt(q,['wrong'],1500),/selected clip/);
assert.equal(JSON.stringify(p),original);
for(const fps of [24,25,30,50,60]) {
 const test={...q,fps}; const result=splitFreeAt(test,keys,1534);
 const cut=Math.round(Math.round(1534*fps/1000)*1000/fps);
 assert(result.patch.free_timeline.clips.every(c=>Number.isInteger(c.duration_ms)));
 assert.equal(result.patch.free_timeline.clips[1].start_ms,cut);
 assert.equal(result.patch.free_timeline.clips.reduce((n,c)=>n+c.duration_ms,0),2000);
}
console.log('PASS frame-aligned split boundaries, repeat cuts on selected right pieces, all overlapping clips and unchanged sources');
